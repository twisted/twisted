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

"""A poll() based implementation of the twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added):

    from twisted.internet import poll
    poll.install()

"""

# System imports
import select, traceback, errno

# Twisted imports
from twisted.python import log, threadable
from twisted.internet import main

# globals
reads = {}
writes = {}
selectables = {}
poller = select.poll()


def _updateRegisteration(fd):
    """Register/unregister an fd with the poller."""
    try:
        poller.unregister(fd)
    except KeyError:
        pass
    
    mask = 0
    if reads.has_key(fd): mask = mask | select.POLLIN
    if writes.has_key(fd): mask = mask | select.POLLOUT
    if mask != 0:
        poller.register(fd, mask)
    else:
        if selectables.has_key(fd): del selectables[fd]

def addReader(reader):
    """Add a FileDescriptor for notification of data available to read.
    """
    fd = reader.fileno()
    if not reads.has_key(fd):
        selectables[fd] = reader
        reads[fd] =  1
        _updateRegisteration(fd)

def addWriter(writer, writes=writes, selectables=selectables):
    """Add a FileDescriptor for notification of data available to write.
    """
    fd = writer.fileno()
    if not writes.has_key(fd):
        selectables[fd] = writer
        writes[fd] =  1
        _updateRegisteration(fd)

def removeReader(reader):
    """Remove a Selectable for notification of data available to read.
    """
    fd = reader.fileno()
    if reads.has_key(fd):
        del reads[fd]
        _updateRegisteration(fd)

def removeWriter(writer, writes=writes):
    """Remove a Selectable for notification of data available to write.
    """
    fd = writer.fileno()
    if writes.has_key(fd):
        del writes[fd]
        _updateRegisteration(fd)

def removeAll():
    """Remove all selectables, and return a list of them."""
    result = selectables.values()
    fds = selectables.keys()
    reads.clear()
    writes.clear()
    selectables.clear()
    for fd in fds:
        poller.unregister(fd)
    return result

def doPoll(timeout,
           reads=reads,
           writes=writes,
           selectables=selectables,
           select=select):
    """Poll the poller for new events."""
    timeout = int(timeout * 1000) # convert seconds to milliseconds

    try:
        l=poller.poll(timeout)
    except select.error, e:
        print repr(e)
        if e[0] == errno.EINTR:
            return
        else:
            raise
    for fd, event in l:
        selectable = selectables[fd]
        log.logOwner.own(selectable)
        
        if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
            why = main.CONNECTION_LOST
        
        try:
            if event & select.POLLIN: why = getattr(selectable, "doRead")()
            if event & select.POLLOUT: why = getattr(selectable, "doWrite")()
            if not selectable.fileno() == fd:
                why = main.CONNECTION_LOST
        except:
            traceback.print_exc(log.logfile)
            why = main.CONNECTION_LOST
        
        if why == main.CONNECTION_LOST:
            removeReader(selectable)
            removeWriter(selectable)
            try:
                selectable.connectionLost()
            except:
                traceback.print_exc(log.logfile)
        
        log.logOwner.disown(selectable)


def install():
    """Install the poll()-based event loop."""
    main.addReader = addReader
    main.addWriter = addWriter
    main.removeReader = removeReader
    main.removeWriter = removeWriter
    main.doSelect = doPoll
    main.removeAll = removeAll


def initThreads():
    """Do initialization for threads."""
    if main.wakerInstalled:
        # make sure waker is registered with us
        removeReader(main.waker)
        addReader(main.waker)

threadable.whenThreaded(initThreads)

__all__ = ["install"]
