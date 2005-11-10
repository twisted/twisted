# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""Support for IReactorProcess for the IOCP proactor.

API Stability: unstable

Maintainer: U{Justin Johnson<mailto:justinjohnson@gmail.com>}

This code is potentially unstable.  I have performed numerous tests
but couldn't get someone who was knowledgable of win32 to review it.
If you run into problems please submit a bug report to
http://twistedmatrix.com/bugs.
"""

# Win32 imports
import win32api
import win32gui
import win32con
import win32file
import win32pipe
import win32process
import win32security
from win32event import CreateEvent, SetEvent, WaitForSingleObject
from win32event import MsgWaitForMultipleObjects, WAIT_OBJECT_0
from win32event import WAIT_TIMEOUT, INFINITE, QS_ALLINPUT, QS_POSTMESSAGE
from win32event import QS_ALLEVENTS

# Zope & Twisted imports
from zope.interface import implements
from twisted.internet import error
from twisted.python import failure, components
from twisted.python.win32 import cmdLineQuote
from twisted.internet.interfaces import IProcessTransport, IConsumer

# sibling imports
import ops
import process_waiter

# System imports
import os
import sys
import time
import itertools

# Counter for uniquely identifying pipes
counter = itertools.count(1)

class Process(object):
    """A process that integrates with the Twisted event loop.

    See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/dllproc/base/creating_a_child_process_with_redirected_input_and_output.asp
    for more info on how to create processes in Windows and access their
    stdout/err/in.  Another good source is http://www.informit.com/articles/article.asp?p=362660&seqNum=2.
    
    Issues:

    If your subprocess is a python program, you need to:

     - Run python.exe with the '-u' command line option - this turns on
       unbuffered I/O. Buffering stdout/err/in can cause problems, see e.g.
       http://support.microsoft.com/default.aspx?scid=kb;EN-US;q1903

     - (is this still true?) If you don't want Windows messing with data passed over
       stdin/out/err, set the pipes to be in binary mode::

        import os, sys, mscvrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)

    """
    implements(IProcessTransport, IConsumer)
    
    # I used this size because abstract.ConnectedSocket did.  I don't
    # know why though.
    bufferSize = 2**2**2**2
    # Per http://www-128.ibm.com/developerworks/linux/library/l-rt4/,
    # an extra 24 bytes are needed to handle write header.  I haven't seen
    # any problems not having the extra 24 bytes though, so I'm not
    # adding it to the size.  I comment here just in case it is discovered
    # to be necessary down the road.
    pipeBufferSize = bufferSize

    def __init__(self, reactor, protocol, command, args, environment, path):
        self.reactor = reactor
        self.protocol = protocol
        self.outBuffer = reactor.AllocateReadBuffer(self.bufferSize)
        self.errBuffer = reactor.AllocateReadBuffer(self.bufferSize)
        # This is the buffer for *reading* stdin, which is only done to
        # determine if the other end of the pipe was closed.
        self.inBuffer = reactor.AllocateReadBuffer(self.bufferSize)
        # IO operation classes
        self.readOutOp = ops.ReadOutOp(self)
        self.readErrOp = ops.ReadErrOp(self)
        self.readInOp = ops.ReadInOp(self)
        self.writeInOp = ops.WriteInOp(self)
        
        self.writeBuffer = ""
        self.writing = False
        self.finished = False
        self.offset = 0
        self.writeBufferedSize = 0
        self.closingStdin = False
        self.closedStdin = False
        self.closedStdout = False
        self.closedStderr = False
        # Stdio handles
        self.hChildStdinRd = None
        self.hChildStdinWr = None
        self.hChildStdinWrDup = None
        self.hChildStdoutRd = None
        self.hChildStdoutWr = None
        self.hChildStdoutRdDup = None
        self.hChildStderrRd = None
        self.hChildStderrWr = None
        self.hChildStderrRdDup = None
        
        self.closedNotifies = 0  # increments to 3 (for stdin, stdout, stderr)
        self.closed = False # set to true when all 3 handles close
        self.exited = False # set to true when WFMO thread gets signalled proc handle.  See doWaitForProcessExit.

        # Set the bInheritHandle flag so pipe handles are inherited. 
        saAttr = win32security.SECURITY_ATTRIBUTES()
        saAttr.bInheritHandle = 1
        
        currentPid = win32api.GetCurrentProcess() # -1 which stands for current process
        self.pid = os.getpid() # unique pid for pipe naming
        
        # Create a pipe for the child process's STDOUT. 
        self.stdoutPipeName = r"\\.\pipe\twisted-iocp-stdout-%d-%d-%d" % (self.pid, counter.next(), time.time())
        self.hChildStdoutRd = win32pipe.CreateNamedPipe(
                self.stdoutPipeName,
                win32con.PIPE_ACCESS_INBOUND | win32con.FILE_FLAG_OVERLAPPED, # open mode
                win32con.PIPE_TYPE_BYTE, # pipe mode
                1, # max instances
                self.pipeBufferSize, # out buffer size
                self.pipeBufferSize, # in buffer size
                0, # timeout 
                saAttr)

        self.hChildStdoutWr = win32file.CreateFile(
                self.stdoutPipeName,
                win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE,
                saAttr,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_OVERLAPPED,
                0);
 
        # Create noninheritable read handle and close the inheritable read 
        # handle.
        self.hChildStdoutRdDup = win32api.DuplicateHandle(
                currentPid, self.hChildStdoutRd,
                currentPid, 0,
                0,
                win32con.DUPLICATE_SAME_ACCESS)
        win32api.CloseHandle(self.hChildStdoutRd);
        self.hChildStdoutRd = self.hChildStdoutRdDup
        
        # Create a pipe for the child process's STDERR.
        self.stderrPipeName = r"\\.\pipe\twisted-iocp-stderr-%d-%d-%d" % (self.pid, counter.next(), time.time())
        self.hChildStderrRd = win32pipe.CreateNamedPipe(
                self.stderrPipeName,
                win32con.PIPE_ACCESS_INBOUND | win32con.FILE_FLAG_OVERLAPPED, # open mode
                win32con.PIPE_TYPE_BYTE, # pipe mode
                1, # max instances
                self.pipeBufferSize, # out buffer size
                self.pipeBufferSize, # in buffer size
                0, # timeout 
                saAttr)
        self.hChildStderrWr = win32file.CreateFile(
                self.stderrPipeName,
                win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE,
                saAttr,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_OVERLAPPED,
                0);

        # Create noninheritable read handle and close the inheritable read 
        # handle.
        self.hChildStderrRdDup = win32api.DuplicateHandle(
                currentPid, self.hChildStderrRd,
                currentPid, 0,
                0,
                win32con.DUPLICATE_SAME_ACCESS)
        win32api.CloseHandle(self.hChildStderrRd)
        self.hChildStderrRd = self.hChildStderrRdDup
        
        # Create a pipe for the child process's STDIN. This one is opened
        # in duplex mode so we can read from it too in order to detect when
        # the child closes their end of the pipe.
        self.stdinPipeName = r"\\.\pipe\twisted-iocp-stdin-%d-%d-%d" % (self.pid, counter.next(), time.time())
        self.hChildStdinWr = win32pipe.CreateNamedPipe(
                self.stdinPipeName,
                win32con.PIPE_ACCESS_DUPLEX | win32con.FILE_FLAG_OVERLAPPED, # open mode
                win32con.PIPE_TYPE_BYTE, # pipe mode
                1, # max instances
                self.pipeBufferSize, # out buffer size
                self.pipeBufferSize, # in buffer size
                0, # timeout 
                saAttr)

        self.hChildStdinRd = win32file.CreateFile(
                self.stdinPipeName,
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE,
                saAttr,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_OVERLAPPED,
                0);
        
        # Duplicate the write handle to the pipe so it is not inherited.
        self.hChildStdinWrDup = win32api.DuplicateHandle(
                currentPid, self.hChildStdinWr, 
                currentPid, 0, 
                0,
                win32con.DUPLICATE_SAME_ACCESS)
        win32api.CloseHandle(self.hChildStdinWr)
        self.hChildStdinWr = self.hChildStdinWrDup
        
        # set the info structure for the new process.  This is where
        # we tell the process to use the pipes for stdout/err/in.
        StartupInfo = win32process.STARTUPINFO()
        StartupInfo.hStdOutput = self.hChildStdoutWr
        StartupInfo.hStdError  = self.hChildStderrWr
        StartupInfo.hStdInput  = self.hChildStdinRd
        StartupInfo.dwFlags = win32process.STARTF_USESTDHANDLES
        
        # create the process
        cmdline = ' '.join([cmdLineQuote(a) for a in args])
        self.hProcess, hThread, dwPid, dwTid = win32process.CreateProcess(
                command,     # name
                cmdline,     # command line
                None,        # process security attributes
                None,        # primary thread security attributes
                1,           # handles are inherited
                0,           # creation flags
                environment, # if NULL, use parent environment
                path,        # current directory
                StartupInfo) # STARTUPINFO pointer 

        # close handles which only the child will use
        win32file.CloseHandle(self.hChildStderrWr)
        win32file.CloseHandle(self.hChildStdoutWr)
        win32file.CloseHandle(self.hChildStdinRd)
        
        # Begin reading on stdout and stderr, before we have output on them.
        self.readOutOp.initiateOp(self.hChildStdoutRd, self.outBuffer)
        self.readErrOp.initiateOp(self.hChildStderrRd, self.errBuffer)
        # Read stdin which was opened in duplex mode so we can detect when
        # the child closed their end of the pipe.
        self.readInOp.initiateOp(self.hChildStdinWr, self.inBuffer)

        # When the process is done, call connectionLost().
        # This function returns right away.  Note I call this after
        # protocol.makeConnection to ensure that the protocol doesn't
        # have processEnded called before protocol.makeConnection.
        self.reactor.processWaiter.beginWait(self.reactor, self.hProcess, self)
        
        # notify protocol by calling protocol.makeConnection and specifying
        # ourself as the transport.
        self.protocol.makeConnection(self)
    
    def signalProcess(self, signalID):
        if signalID in ("INT", "TERM", "KILL"):
            win32process.TerminateProcess(self.hProcess, 1)

    def startWriting(self):
        if not self.writing:
            self.writing = True
            b = buffer(self.writeBuffer, self.offset, self.offset + self.bufferSize)
            self.writeInOp.initiateOp(self.hChildStdinWr, b)

    def stopWriting(self):
        self.writing = False

    def writeDone(self, bytes):
        self.writing = False
        self.offset += bytes
        self.writeBufferedSize -= bytes
        if self.offset == len(self.writeBuffer):
            self.writeBuffer = ""
            self.offset = 0
        if self.writeBuffer == "":
            self.writing = False
            # If there's nothing else to write and we're closing,
            # do it now.
            if self.closingStdin:
                self._closeStdin()
                self.connectionLostNotify()
        else:
            self.startWriting()
            
    def write(self, data):
        """Write data to the process' stdin."""
        self.writeBuffer += data
        self.writeBufferedSize += len(data)
        if not self.writing:
            self.startWriting()

    def writeSequence(self, seq):
        """Write a list of strings to the physical connection.

        If possible, make sure that all of the data is written to
        the socket at once, without first copying it all into a
        single string.
        """
        self.write("".join(seq))

    def closeStdin(self):
        """Close the process' stdin."""
        if not self.closingStdin:
            self.closingStdin = True
            if not self.writing:
                self._closeStdin()
                self.connectionLostNotify()

    def _closeStdin(self):
        if hasattr(self, "hChildStdinWr"):
            win32file.CloseHandle(self.hChildStdinWr)
            del self.hChildStdinWr
            self.closingStdin = False
            self.closedStdin = True

    def closeStderr(self):
        if hasattr(self, "hChildStderrRd"):
            win32file.CloseHandle(self.hChildStderrRd)
            del self.hChildStderrRd
            self.closedStderr = True
            self.connectionLostNotify()

    def closeStdout(self):
        if hasattr(self, "hChildStdoutRd"):
            win32file.CloseHandle(self.hChildStdoutRd)
            del self.hChildStdoutRd
            self.closedStdout = True
            self.connectionLostNotify()

    def loseConnection(self):
        """Close the process' stdout, in and err."""
        self.closeStdin()
        self.closeStdout()
        self.closeStderr()

    def outConnectionLost(self):
        self.closeStdout() # in case process closed it, not us
        self.protocol.outConnectionLost()

    def errConnectionLost(self):
        self.closeStderr() # in case process closed it
        self.protocol.errConnectionLost()

    def inConnectionLost(self):
        self._closeStdin()
        self.protocol.inConnectionLost()
        self.connectionLostNotify()

    def connectionLostNotify(self):
        """Will be called 3 times, for stdout/err/in."""
        self.closedNotifies = self.closedNotifies + 1
        if self.closedNotifies == 3:
            self.closed = 1
            if self.exited:
                self.connectionLost()
        
    def processEnded(self):
        self.exited = True
        # If all 3 stdio handles are closed, call connectionLost
        if self.closed:
            self.connectionLost()
            
    def connectionLost(self, reason=None):
        """Shut down resources."""
        # Get the exit status and notify the protocol
        exitCode = win32process.GetExitCodeProcess(self.hProcess)
        if exitCode == 0:
            err = error.ProcessDone(exitCode)
        else:
            err = error.ProcessTerminated(exitCode)
        self.protocol.processEnded(failure.Failure(err))
    
    ## IConsumer
    
    def registerProducer(self, producer, streaming):
        pass

    def unregisterProducer(self):
        pass


components.backwardsCompatImplements(Process)
