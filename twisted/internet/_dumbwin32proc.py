# -*- test-case-name: twisted.test.test_process -*-
"""

http://isometric.sixsided.org/_/gates_in_the_head/

"""

import itertools
import os

# Win32 imports
from win32file import WSAEventSelect, FD_READ, FD_WRITE, FD_CLOSE, \
                      FD_ACCEPT, FD_CONNECT
from win32event import CreateEvent, MsgWaitForMultipleObjects, \
                       WAIT_OBJECT_0, WAIT_TIMEOUT, INFINITE, QS_ALLINPUT, QS_ALLEVENTS
import win32api
import win32con
import win32event
import win32file
import win32pipe
import win32process
import win32security
import pywintypes
import msvcrt
import win32gui

# security attributes for pipes
PIPE_ATTRS_INHERITABLE = win32security.SECURITY_ATTRIBUTES()
PIPE_ATTRS_INHERITABLE.bInheritHandle = 1

from zope.interface import implements
from twisted.internet.interfaces import IProcessTransport

from twisted.python import components
from twisted.python.win32 import cmdLineQuote

from twisted.internet import error
from twisted.python import failure

def debug(msg):
    import sys
    print msg
    sys.stdout.flush()

_pipeNameCounter = itertools.count()

def _genPipeName():
    return u'Twisted-%d-%d' % (os.getpid(), _pipeNameCounter.next())

def _pseudoAnonymousPipe():
    # Does nothing, don't call it, this is just notes for future implementors
    name = _genPipeName()
    openMode = win32pipe.PIPE_ACCESS_INBOUND
    pipeMode = win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_NOWAIT
    nMaxInstances = 1
    nOutBufferSize = 8192
    nInBufferSize = 8192
    nDefaultTimeout = 0
    readPipe = win32pipe.CreateNamedPipe(name,
                                         openMode,
                                         pipeMode,
                                         nMaxInstances,
                                         nOutBufferSize,
                                         nInBufferSize,
                                         nDefaultTimeout,
                                         PIPE_ATTRS_INHERITABLE)

class Process:
    """A process that integrates with the Twisted event loop.

    If your subprocess is a python program, you need to:

     - Run python.exe with the '-u' command line option - this turns on
       unbuffered I/O. Buffering stdout/err/in can cause problems, see e.g.
       http://support.microsoft.com/default.aspx?scid=kb;EN-US;q1903

     - If you don't want Windows messing with data passed over
       stdin/out/err, set the pipes to be in binary mode::

        import os, sys, mscvrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)

    """
    implements(IProcessTransport)

    buffer = ''

    def __init__(self, reactor, protocol, command, args, environment, path):
        self.reactor = reactor
        self.protocol = protocol

        # security attributes for pipes
        sAttrs = win32security.SECURITY_ATTRIBUTES()
        sAttrs.bInheritHandle = 1

        # create the pipes which will connect to the secondary process
        self.hStdoutR, hStdoutW = win32pipe.CreatePipe(sAttrs, 0)
        self.hStderrR, hStderrW = win32pipe.CreatePipe(sAttrs, 0)
        hStdinR,  self.hStdinW  = win32pipe.CreatePipe(sAttrs, 0)

        win32pipe.SetNamedPipeHandleState(self.hStdinW,
                                          win32pipe.PIPE_NOWAIT,
                                          None,
                                          None)

        # set the info structure for the new process.
        StartupInfo = win32process.STARTUPINFO()
        StartupInfo.hStdOutput = hStdoutW
        StartupInfo.hStdError  = hStderrW
        StartupInfo.hStdInput  = hStdinR
        StartupInfo.dwFlags = win32process.STARTF_USESTDHANDLES

        # Create new handles whose inheritance property is false
        pid = win32api.GetCurrentProcess()

        tmp = win32api.DuplicateHandle(pid, self.hStdoutR, pid, 0, 0, win32con.DUPLICATE_SAME_ACCESS)
        win32file.CloseHandle(self.hStdoutR)
        self.hStdoutR = tmp

        tmp = win32api.DuplicateHandle(pid, self.hStderrR, pid, 0, 0, win32con.DUPLICATE_SAME_ACCESS)
        win32file.CloseHandle(self.hStderrR)
        self.hStderrR = tmp

        tmp = win32api.DuplicateHandle(pid, self.hStdinW, pid, 0, 0, win32con.DUPLICATE_SAME_ACCESS)
        win32file.CloseHandle(self.hStdinW)
        self.hStdinW = tmp

        # Add the specified environment to the current environment - this is
        # necessary because certain operations are only supported on Windows
        # if certain environment variables are present.
        env = os.environ.copy()
        env.update(environment or {})

        # create the process
        cmdline = ' '.join([cmdLineQuote(a) for a in args])
        self.hProcess, hThread, dwPid, dwTid = win32process.CreateProcess(command, cmdline, None, None, 1, 0, env, path, StartupInfo)
        win32file.CloseHandle(hThread)

        # close handles which only the child will use
        win32file.CloseHandle(hStderrW)
        win32file.CloseHandle(hStdoutW)
        win32file.CloseHandle(hStdinR)

        self.outQueue = []
        self.closed = 0
        self.closedNotifies = 0

        # notify protocol
        self.protocol.makeConnection(self)
        from twisted.internet.task import LoopingCall
        self._lc = LoopingCall(self._checkPipes)
        self._lc.start(0.01)

        # (maybe?) a good idea in win32er, otherwise not
        # self.reactor.addEvent(self.hProcess, self, 'inConnectionLost')

    def _checkPipes(self):
        MAX_THROUGHPUT = 8192
        throughput = 0
        current = 1
        # This stupidness is to preseve decent throughput when you have a
        # process writing to itself; the tests will time out otherwise.  Really
        # this should be accomplished by scaling down the interval of the
        # looping call.
        while current and throughput < MAX_THROUGHPUT:
            current = 0
            current += self.doReadOut()
            current += self.doReadErr()
            current += self.doWrite()
            throughput += current
        self.reapProcess()
        # debug("ONE PASS %d" % (throughput,))

    def signalProcess(self, signalID):
        if signalID in ("INT", "TERM", "KILL"):
            win32process.TerminateProcess(self.hProcess, 1)

    def write(self, data):
        """Write data to the process' stdin."""
        if self.outQueue and self.outQueue[-1] is None:
            return
        self.outQueue.append(data)

    def writeSequence(self, seq):
        """Write data to the process' stdin."""
        self.outQueue.extend(seq)

    def closeStdin(self):
        """Close the process' stdin.
        """
        self.outQueue.append(None)

    def closeStderr(self):
        if hasattr(self, "hStderrR"):
            win32file.CloseHandle(self.hStderrR)
            del self.hStderrR
            self.errConnectionLost()

    def closeStdout(self):
        if hasattr(self, "hStdoutR"):
            win32file.CloseHandle(self.hStdoutR)
            del self.hStdoutR
            self.outConnectionLost()

    def loseConnection(self):
        """Close the process' stdout, in and err."""
        self.closeStdin()
        self.closeStdout()
        self.closeStderr()

    def outConnectionLost(self):
        self.protocol.childConnectionLost(1)
        self.connectionLostNotify()

    def errConnectionLost(self):
        self.protocol.childConnectionLost(2)
        self.connectionLostNotify()

    def inConnectionLost(self):
        if hasattr(self, "hStdinW"):
            win32file.CloseHandle(self.hStdinW)
            del self.hStdinW
        self.protocol.childConnectionLost(0)
        self.connectionLostNotify()

    def connectionLostNotify(self):
        """Will be called 3 times, by stdout/err threads and process handle."""
        self.closedNotifies = self.closedNotifies + 1
        if self.closedNotifies == 3:
            self.closed = 1

    def reapProcess(self):
        if not self.closed:
            return
        if win32event.WaitForSingleObject(self.hProcess, 0) != win32event.WAIT_OBJECT_0:
            return
        self._lc.stop()
        exitCode = win32process.GetExitCodeProcess(self.hProcess)
        # self.reactor.removeEvent(self.hProcess)
        if exitCode == 0:
            err = error.ProcessDone(exitCode)
        else:
            err = error.ProcessTerminated(exitCode)
        self.protocol.processEnded(failure.Failure(err))

    def doWrite(self):
        numBytesWritten = 0
        if not hasattr(self, 'hStdinW'):
            return numBytesWritten
        if not self.outQueue:
            # mumble, something about producer support
            try:
                win32file.WriteFile(self.hStdinW, '', None)
            except pywintypes.error:
                self.inConnectionLost()
                return numBytesWritten
        while self.outQueue:
            data = self.outQueue.pop(0)
            if data == None:
                self.inConnectionLost()
                break
            errCode = 0
            try:
                errCode, nBytesWritten = win32file.WriteFile(self.hStdinW, data, None)
            except win32api.error:
                self.inConnectionLost()
                break
            else:
                # assert not errCode, "wtf an error code???"
                numBytesWritten += nBytesWritten
                if len(data) > nBytesWritten:
                    self.outQueue.insert(0, data[nBytesWritten:])
                    break
        return numBytesWritten

    def _doReadPipe(self, pipeName, received, lost):
        numBytesRead = 0
        pipe = getattr(self, pipeName, None)
        if pipe is None:
            return numBytesRead
        finished = 0
        while 1:
            try:
                buffer, bytesToRead, result = win32pipe.PeekNamedPipe(pipe, 1)
                # finished = (result == -1)
                if not bytesToRead:
                    break
                hr, data = win32file.ReadFile(pipe, bytesToRead, None)
                numBytesRead += len(data)
                received(data)
            except win32api.error:
                finished = 1
                break

        if finished:
            lost()
        return numBytesRead

    def doReadOut(self):
        return self._doReadPipe('hStdoutR', self.protocol.outReceived, self.closeStdout)

    def doReadErr(self):
        return self._doReadPipe('hStderrR', self.protocol.errReceived, self.closeStderr)

components.backwardsCompatImplements(Process)
