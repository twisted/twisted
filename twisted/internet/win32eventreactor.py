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

This requires win32all to be installed.

TODO:
1. Pass tests.
2. WaitForMultipleObjects can only handle 64 objects, so we need threads.
3. Event loop handling of writes is *very* problematic.
4. Support GUI events.
5. Replace icky socket loopback waker with event based waker.
6. Switch everyone to a decent OS so we don't have to deal with insane APIs.
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
from twisted.internet import abstract, main, task, default, process
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


class Win32Reactor(default.PosixReactorBase):
    """Reactor that uses Win32 event APIs."""
    
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
        if timeout is None:
            #timeout = INFINITE
            timeout = 5000
        else:
            timeout = int(timeout * 1000)

        if not (events or writes):
            # sleep so we don't suck up CPU time
            time.sleep(timeout / 1000.0)
            return

        canDoMoreWrites = 0
        for fd in writes.keys():
            log.logOwner.own(fd)
            closed = 0
            try:
                closed = fd.doWrite()
            except:
                log.deferr()
                closed = 1

            if closed:
                self.removeReader(fd)
                self.removeWriter(fd)
                try:
                    fd.connectionLost()
                except:
                    log.deferr()
            elif closed is None:
                canDoMoreWrites = 1
            log.logOwner.disown(fd)

        if canDoMoreWrites:
            timeout = 0

        if not events:
            time.sleep(timeout / 1000.0)
            return

        handles = events.keys()
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
                self.removeReader(fd)
                self.removeWriter(fd)
                try:
                    fd.connectionLost()
                except:
                    log.deferr()

            log.logOwner.disown(fd)

    doIteration = doWaitForMultipleEvents

    def spawnProcess(self, processProtocol, executable, args=(), env={}):
        """Spawn a process."""
        Process(self, processProtocol, executable, args, env)


def install():
    threadable.init(1)
    # change when we redo process stuff - process is probably
    # borked anyway.
    process.Process = Process
    r = Win32Reactor()
    import main
    main.installReactor(r)


class Process(abstract.FileDescriptor):
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
    
    buffer = ''
    
    def __init__(self, reactor, protocol, command, args, environment):
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
        self.hProcess, hThread, dwPid, dwTid = win32process.CreateProcess(None, cmdline, None, None, 1, 0, environment, None, StartupInfo)
        
        # close handles which only the child will use
        win32file.CloseHandle(hStderrW)
        win32file.CloseHandle(hStdoutW)
        win32file.CloseHandle(hStdinR)

        self.outQueue = Queue.Queue()
        self.closed = 0
        self.closedNotifies = 0

        # notify protocol
        self.protocol.makeConnection(self)
        
        self.reactor.addEvent(self.hProcess, self, self.connectionLostNotify)
        threading.Thread(target=self.doWrite).start()
        threading.Thread(target=self.doReadOut).start()
        threading.Thread(target=self.doReadErr).start()
    
    def write(self, data):
        """Write data to the process' stdin."""
        self.outQueue.put(data)
    
    def closeStdin(self):
        """Close the process' stdin."""
        self.outQueue.put(None)

    loseConnection = closeStdin
    
    def outConnectionLost(self):
        self.protocol.connectionLost()
        self.connectionLostNotify()

    def errConnectionLost(self):
        self.protocol.errConnectionLost()
        self.connectionLostNotify()
    
    def connectionLostNotify(self):
        """Will be called 3 times, by stdout/err threads and process handle."""
        self.closedNotifies = self.closedNotifies + 1
        if self.closedNotifies == 3:
            self.closed = 1
            self.connectionLost()
    
    def connectionLost(self):
        """Shut down resources."""
        self.reactor.removeEvent(self.hProcess)
        del self.reactor
        abstract.FileDescriptor.connectionLost(self)
        self.closeStdin()
        win32file.CloseHandle(self.hStdoutR)
        win32file.CloseHandle(self.hStderrR)
        self.protocol.processEnded()
        del self.protocol
    
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
        while 1:
            try:
                buffer, bytesToRead, result = win32pipe.PeekNamedPipe(self.hStdoutR, 1)
                if bytesToRead == 0 and result != -1:
                    bytesToRead = 1
                hr, data = win32file.ReadFile(self.hStdoutR, bytesToRead, None)
            except win32api.error:
                result = -1
            else:
                task.schedule(self.protocol.dataReceived, data)
            
            if result == -1:
                task.schedule(self.outConnectionLost)
                return
    
    def doReadErr(self):
        """Runs in thread."""
        while 1:
            try:
                buffer, bytesToRead, result = win32pipe.PeekNamedPipe(self.hStderrR, 1)
                if bytesToRead == 0 and result != -1:
                    bytesToRead = 1
                hr, data = win32file.ReadFile(self.hStderrR, bytesToRead, None)
            except win32api.error:
                result = -1
            else:
                task.schedule(self.protocol.errReceived, data)
            
            if result == -1:
                task.schedule(self.errConnectionLost)
                return
            


__all__ = ["Win32Reactor", "install"]

