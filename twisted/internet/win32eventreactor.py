# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""A win32event based implementation of the Twisted main loop.

This requires win32all or ActivePython to be installed.

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}


LIMITATIONS:
 1. WaitForMultipleObjects and thus the event loop can only handle 64 objects.
 2. Process running has some problems (see Process docstring).


TODO:
 1. Event loop handling of writes is *very* problematic (this is causing failed tests).
    Switch to doing it the correct way, whatever that means (see below).
 2. Replace icky socket loopback waker with event based waker (use dummyEvent object)
 3. Switch everyone to using Free Software so we don't have to deal with proprietary APIs.


ALTERNATIVE SOLUTIONS:
 - IIRC, sockets can only be registered once. So we switch to a structure
   like the poll() reactor, thus allowing us to deal with write events in
   a decent fashion. This should allow us to pass tests, but we're still
   limited to 64 events.

Or:

 - Instead of doing a reactor, we make this an addon to the default reactor.
   The WFMO event loop runs in a separate thread. This means no need to maintain
   separate code for networking, 64 event limit doesn't apply to sockets,
   we can run processes and other win32 stuff in default event loop. The
   only problem is that we're stuck with the icky socket based waker.
   Another benefit is that this could be extended to support >64 events
   in a simpler manner than the previous solution.

The 2nd solution is probably what will get implemented.
"""

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

# Twisted imports
from twisted.internet import abstract, default, main, error
from twisted.python import log, threadable, failure
from twisted.internet.interfaces import IReactorFDSet

# System imports
import os
import threading
import Queue
import string
import time
import sys


# globals
reads = {}
writes = {}
events = {}


class Win32Reactor(default.PosixReactorBase):
    """Reactor that uses Win32 event APIs."""

    __implements__ = (default.PosixReactorBase.__implements__, IReactorFDSet)

    dummyEvent = CreateEvent(None, 0, 0, None)

    def _makeSocketEvent(self, fd, action, why, events=events):
        """Make a win32 event object for a socket."""
        event = CreateEvent(None, 0, 0, None)
        WSAEventSelect(fd, event, why)
        events[event] = (fd, action)
        return event

    def addEvent(self, event, fd, action, events=events):
        """Add a new win32 event to the event loop."""
        events[event] = (fd, action)

    def removeEvent(self, event):
        """Remove an event."""
        del events[event]

    def addReader(self, reader, reads=reads):
        """Add a socket FileDescriptor for notification of data available to read.
        """
        if not reads.has_key(reader):
            reads[reader] = self._makeSocketEvent(reader, reader.doRead, FD_READ|FD_ACCEPT|FD_CONNECT|FD_CLOSE)

    def addWriter(self, writer, writes=writes):
        """Add a socket FileDescriptor for notification of data available to write.
        """
        if not writes.has_key(writer):
            writes[writer] = 1

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        if reads.has_key(reader):
            del events[reads[reader]]
            del reads[reader]

    def removeWriter(self, writer, writes=writes):
        """Remove a Selectable for notification of data available to write.
        """
        if writes.has_key(writer):
            del writes[writer]

    def removeAll(self):
        """Remove all selectables, and return a list of them."""
        result = reads.keys() + writes.keys()
        reads.clear()
        writes.clear()
        events.clear()
        return result

    def doWaitForMultipleEvents(self, timeout,
                                reads=reads,
                                writes=writes):
        log.msg(channel='system', event='iteration', reactor=self)
        if timeout is None:
            #timeout = INFINITE
            timeout = 100
        else:
            timeout = int(timeout * 1000)

        if not (events or writes):
            # sleep so we don't suck up CPU time
            time.sleep(timeout / 1000.0)
            return

        canDoMoreWrites = 0
        for fd in writes.keys():
            if log.callWithLogger(fd, self._runWrite, fd):
                canDoMoreWrites = 1

        if canDoMoreWrites:
            timeout = 0

        handles = events.keys() or [self.dummyEvent]
        val = MsgWaitForMultipleObjects(handles, 0, timeout, QS_ALLINPUT | QS_ALLEVENTS)
        if val == WAIT_TIMEOUT:
            return
        elif val == WAIT_OBJECT_0 + len(handles):
            exit = win32gui.PumpWaitingMessages()
            if exit:
                self.callLater(0, self.stop)
                return
        elif val >= WAIT_OBJECT_0 and val < WAIT_OBJECT_0 + len(handles):
            fd, action = events[handles[val - WAIT_OBJECT_0]]
            closed = 0
            log.callWithLogger(fd, self._runAction, action, fd)

    def _runWrite(self, fd):
        closed = 0
        try:
            closed = fd.doWrite()
        except:
            closed = sys.exc_info()[1]
            log.deferr()

        if closed:
            self.removeReader(fd)
            self.removeWriter(fd)
            try:
                fd.connectionLost(failure.Failure(closed))
            except:
                log.deferr()
        elif closed is None:
            return 1

    def _runAction(self, action, fd):
            try:
                closed = action()
            except:
                closed = sys.exc_info()[1]
                log.deferr()

            if closed:
                self.removeReader(fd)
                self.removeWriter(fd)
                try:
                    fd.connectionLost(failure.Failure(closed))
                except:
                    log.deferr()

    doIteration = doWaitForMultipleEvents

    def spawnProcess(self, processProtocol, executable, args=(), env={}, path=None, usePTY=0):
        """Spawn a process."""
        Process(self, processProtocol, executable, args, env, path)


def install():
    threadable.init(1)
    r = Win32Reactor()
    import main
    main.installReactor(r)


class Process(abstract.FileDescriptor):
    """A process that integrates with the Twisted event loop.

    Issues:

     - stdin close is actually signalled by process shutdown, which is wrong.
       Solution is to register stdin pipe with event loop and check for the
       correct event type - this needs to be implemented.

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

        # create the process
        cmdline = "%s %s" % (command, string.join(args[1:], ' '))
        self.hProcess, hThread, dwPid, dwTid = win32process.CreateProcess(None, cmdline, None, None, 1, 0, environment, path, StartupInfo)

        # close handles which only the child will use
        win32file.CloseHandle(hStderrW)
        win32file.CloseHandle(hStdoutW)
        win32file.CloseHandle(hStdinR)

        self.outQueue = Queue.Queue()
        self.closed = 0
        self.closedNotifies = 0

        # notify protocol
        self.protocol.makeConnection(self)

        self.reactor.addEvent(self.hProcess, self, self.inConnectionLost)
        threading.Thread(target=self.doWrite).start()
        threading.Thread(target=self.doReadOut).start()
        threading.Thread(target=self.doReadErr).start()

    def signalProcess(self, signalID):
        if signalID in ("INT", "TERM", "KILL"):
            win32process.TerminateProcess(self.hProcess, 1)

    def write(self, data):
        """Write data to the process' stdin."""
        self.outQueue.put(data)

    def closeStdin(self):
        """Close the process' stdin."""
        self.outQueue.put(None)

    def closeStderr(self):
        if hasattr(self, "hStderrR"):
            win32file.CloseHandle(self.hStderrR)
            del self.hStderrR

    def closeStdout(self):
        if hasattr(self, "hStdoutR"):
            win32file.CloseHandle(self.hStdoutR)
            del self.hStdoutR

    def loseConnection(self):
        """Close the process' stdout, in and err."""
        self.closeStdin()
        self.closeStdout()
        self.closeStderr()

    def outConnectionLost(self):
        self.closeStdout() # in case process closed it, not us
        self.protocol.outConnectionLost()
        self.connectionLostNotify()

    def errConnectionLost(self):
        self.closeStderr() # in case processed closed it
        self.protocol.errConnectionLost()
        self.connectionLostNotify()

    def _closeStdin(self):
        if hasattr(self, "hStdinW"):
            win32file.CloseHandle(self.hStdinW)
            del self.hStdinW
            self.outQueue.put(None)

    def inConnectionLost(self):
        self._closeStdin()
        self.protocol.inConnectionLost()
        self.connectionLostNotify()

    def connectionLostNotify(self):
        """Will be called 3 times, by stdout/err threads and process handle."""
        self.closedNotifies = self.closedNotifies + 1
        if self.closedNotifies == 3:
            self.closed = 1
            self.connectionLost()

    def connectionLost(self, reason=None):
        """Shut down resources."""
        exitCode = win32process.GetExitCodeProcess(self.hProcess)
        self.reactor.removeEvent(self.hProcess)
        abstract.FileDescriptor.connectionLost(self, reason)
        if exitCode == 0:
            err = error.ProcessDone(exitCode)
        else:
            err = error.ProcessTerminated(exitCode)
        self.protocol.processEnded(failure.Failure(err))

    def doWrite(self):
        """Runs in thread."""
        while 1:
            data = self.outQueue.get()
            if data == None:
                break
            try:
                win32file.WriteFile(self.hStdinW, data, None)
            except win32api.error:
                break

        self._closeStdin()

    def doReadOut(self):
        """Runs in thread."""
        while 1:
            try:
                finished = 0
                buffer, bytesToRead, result = win32pipe.PeekNamedPipe(self.hStdoutR, 1)
                finished = (result == -1) and not bytesToRead
                if bytesToRead == 0 and result != -1:
                    bytesToRead = 1
                hr, data = win32file.ReadFile(self.hStdoutR, bytesToRead, None)
            except win32api.error:
                finished = 1
            else:
                self.reactor.callFromThread(self.protocol.outReceived, data)

            if finished:
                self.reactor.callFromThread(self.outConnectionLost)
                return

    def doReadErr(self):
        """Runs in thread."""
        while 1:
            try:
                finished = 0
                buffer, bytesToRead, result = win32pipe.PeekNamedPipe(self.hStderrR, 1)
                finished = (result == -1) and not bytesToRead
                if bytesToRead == 0 and result != -1:
                    bytesToRead = 1
                hr, data = win32file.ReadFile(self.hStderrR, bytesToRead, None)
            except win32api.error:
                finished = 1
            else:
                self.reactor.callFromThread(self.protocol.errReceived, data)

            if finished:
                self.reactor.callFromThread(self.errConnectionLost)
                return



__all__ = ["Win32Reactor", "install"]
