
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

"""A win32event based implementation of the twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added):

    from twisted.internet import win32
    win32.install()

"""

# Win32 imports
from win32file import WSAEventSelect, FD_READ, FD_WRITE, FD_CLOSE, \
                      FD_ACCEPT, FD_CONNECT
from win32event import CreateEvent, WaitForMultipleObjects, \
                       WAIT_OBJECT_0, WAIT_TIMEOUT, INFINITE
import win32api
import win32con
import win32event
import win32file
import win32pipe
import win32process
import win32security
import pywintypes
import msvcrt

# Twisted imports
from twisted.internet import abstract, main
from twisted.python import log, threadable

# System imports
import os
import threading
import Queue
import string
import time


# globals
reads = {}
writes = {}
events = {}


def _makeSocketEvent(fd, action, why, events=events):
    """Make a win32 event object for a socket."""
    event = CreateEvent(None, 0, 0, None)
    WSAEventSelect(fd, event, why)
    events[event] = (fd, action)
    return event

def addEvent(event, fd, action, events=events):
    """Add a new win32 event to the event loop."""
    events[event] = (fd, action)

def removeEvent(event):
    """Remove an event."""
    del events[event]

def addReader(reader, reads=reads):
    """Add a socket FileDescriptor for notification of data available to read.
    """
    if not reads.has_key(reader):
        reads[reader] = _makeSocketEvent(reader, reader.doRead, FD_READ|FD_ACCEPT|FD_CONNECT|FD_CLOSE)
        
def addWriter(writer, writes=writes):
    """Add a socket FileDescriptor for notification of data available to write.
    """
    if not writes.has_key(writer):
        writes[writer] =_makeSocketEvent(writer, writer.doWrite, FD_WRITE|FD_CLOSE)

def removeReader(reader):
    """Remove a Selectable for notification of data available to read.
    """
    if reads.has_key(reader):
        del events[reads[reader]]
        del reads[reader]

def removeWriter(writer, writes=writes):
    """Remove a Selectable for notification of data available to write.
    """
    if writes.has_key(writer):
        del events[writes[writer]]
        del writes[writer]

def removeAll():
    """Remove all selectables, and return a list of them."""
    result = reads.keys() + writes.keys()
    reads.clear()
    writes.clear()
    events.clear()
    return result

def doWaitForMultipleEvents(timeout,
                            reads=reads,
                            writes=writes):
    if timeout is None:
        #timeout = INFINITE
        timeout = 5000
    else:
        timeout = int(timeout * 1000)
    
    handles = events.keys()
    if not handles:
        # sleep so we don't suck up CPU time
        time.sleep(timeout / 1000.0)
        return
    val = WaitForMultipleObjects(handles, 0, timeout)
    if val == WAIT_TIMEOUT:
        return
    elif val >= WAIT_OBJECT_0 and val < WAIT_OBJECT_0 + len(handles):
        fd, action = events[handles[val - WAIT_OBJECT_0]]
        closed = 0
        log.logOwner.own(fd)
        try:
            closed = action()
        except:
            log.deferr()
            closed = 1

        if closed:
            removeReader(fd)
            removeWriter(fd)
            try:
                fd.connectionLost()
            except:
                log.deferr()

        log.logOwner.disown(fd)


class Process(abstract.FileDescriptor):
    """A process that integrates with the Twisted event loop."""
    
    buffer = ''
    
    def __init__(self, command, args, environment, path):
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
        cmdline = "%s %s" % (command, string.join(args, ' '))
        hProcess, hThread, dwPid, dwTid = win32process.CreateProcess(None, cmdline, None, None, 1, 0, environment, path, StartupInfo)
        
        # close handles which only the child will use
        win32file.CloseHandle(hStderrW)
        win32file.CloseHandle(hStdoutW)
        win32file.CloseHandle(hStdinR)

        self.outQueue = Queue.Queue()
        self.closed = 0
        self.stdoutClosed = 0
        self.stderrClosed = 0
        
        threading.Thread(target=self.doWrite).start()
        addEvent(self.hStdoutR, self, self.doReadOut)
        addEvent(self.hStderrR, self, self.doReadErr)
    
    def write(self, data):
        """Write data to the process' stdin."""
        self.outQueue.put(data)
    
    def closeStdin(self):
        """Close the process' stdin."""
        self.outQueue.put(None)
    
    def connectionLost(self):
        """Will be called twice, by the stdout and stderr threads."""
        if not self.closed:
            removeEvent(self.hStdoutR)
            removeEvent(self.hStderrR)
            abstract.FileDescriptor.connectionLost(self)
            self.closed = 1
            self.closeStdin()
            win32file.CloseHandle(self.hStdoutR)
            win32file.CloseHandle(self.hStderrR)
    
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
        
        win32file.CloseHandle(self.hStdinW)
    
    def doReadOut(self):
        """Runs in thread."""
        try:
            hr, data = win32file.ReadFile(self.hStdoutR, 8192, None)
        except win32api.error:
            self.stdoutClosed = 1
            if self.stderrClosed:
                return main.CONNECTION_LOST
            else:
                return
        self.handleChunk(data)
    
    def doReadErr(self):
        """Runs in thread."""
        try:
            hr, data = win32file.ReadFile(self.hStderrR, 8192, None)
        except win32api.error:
            self.stderrClosed = 1
            if self.stdoutClosed:
                return main.CONNECTION_LOST
            else:
                return
        self.handleError(data)


def install():
    """Install the win32 event loop."""
    import main, process
    main.addReader = addReader
    main.addWriter = addWriter
    main.removeReader = removeReader
    main.removeWriter = removeWriter
    main.doSelect = doWaitForMultipleEvents
    main.removeAll = removeAll
    process.Process = Process


def initThreads():
    """Do initialization for threads."""
    import main
    if main.wakerInstalled:
        # make sure waker is registered with us
        # XXX use a real win32 waker, an event, instead of the icky socket hack
        removeReader(main.waker)
        addReader(main.waker)

threadable.whenThreaded(initThreads)


__all__ = ["install"]

