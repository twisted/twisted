"""A poll() based implementation of the twisted main loop."""

# System imports
import select, traceback

# Twisted imports
from twisted.python import log
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


def doPoll(timeout,
           reads=reads,
           writes=writes,
           selectables=selectables,
           select=select):
    """Poll the poller for new events."""
    timeout = int(timeout * 1000) # convert seconds to milliseconds

    for fd, event in poller.poll(timeout):
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
