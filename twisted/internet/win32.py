
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

# System imports
import time

# Twisted imports
from twisted.python import log, threadable


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
        timeout = timeout * 1000
    
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


def install():
    """Install the win32 event loop."""
    import main
    main.addReader = addReader
    main.addWriter = addWriter
    main.removeReader = removeReader
    main.removeWriter = removeWriter
    main.doSelect = doWaitForMultipleEvents
    main.removeAll = removeAll


def initThreads():
    """Do initialization for threads."""
    import main
    if main.wakerInstalled:
        # make sure waker is registered with us
        removeReader(main.waker)
        addReader(main.waker)

threadable.whenThreaded(initThreads)


__all__ = ["install"]

