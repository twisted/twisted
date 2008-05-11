# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A libevent based implementation of the twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added)::

    from twisted.internet import libeventreactor
    libeventreactor.install()

API Stability: stable

Maintainer: U{Thomas Herve <mailto:therve@free.fr>}
"""

# System imports
import sys

from zope.interface import implements

from twisted.internet import posixbase, main, error
from twisted.python import libevent, log
from twisted.internet.interfaces import IReactorFDSet
from twisted.python.runtime import platformType



class LibEventReactor(posixbase.PosixReactorBase):
    """
    A reactor that uses libevent.

    @ivar _selectables: A dictionary mapping integer file descriptors to
        instances of L{FileDescriptor} which have been registered with the
        reactor.  All L{FileDescriptors} which are currently receiving read or
        write readiness notifications will be present as values in this
        dictionary.

    @ivar _reads: A dictionary mapping integer file descriptors to libevent
        event objects.  Keys in this dictionary will be registered with
        libevent for read readiness notifications which will
        be dispatched to the corresponding L{FileDescriptor} instances in
        C{_selectables}.

    @ivar _writes: A dictionary mapping integer file descriptors to libevent
        event objects.  Keys in this dictionary will be registered with
        libevent for write readiness notifications which will
        be dispatched to the corresponding L{FileDescriptor} instances in
        C{_selectables}.
    """
    implements(IReactorFDSet)

    def __init__(self):
        """
        Initialize reactor and local fd storage.
        """
        # These inits really ought to be before
        # L{posixbase.PosixReactorBase.__init__} call, because it adds the
        # waker in the process
        self._reads = {}
        self._writes = {}
        self._selectables = {}
        posixbase.PosixReactorBase.__init__(self)


    def _add(self, xer, flags, mdict):
        """
        Create the event for reader/writer.
        """
        fd = xer.fileno()
        if fd not in mdict:
            event = libevent.createEvent(fd, flags, self._eventCallback)
            mdict[fd] = event
            event.addToLoop()
            self._selectables[fd] = xer


    def addReader(self, reader):
        """
        Add a FileDescriptor for notification of data available to read.
        """
        self._add(reader, libevent.EV_READ|libevent.EV_PERSIST, self._reads)


    def addWriter(self, writer):
        """
        Add a FileDescriptor for notification of data available to write.
        """
        self._add(writer, libevent.EV_WRITE|libevent.EV_PERSIST, self._writes)


    def _remove(self, selectable, mdict, other):
        """
        Remove an event if found.
        """
        fd = selectable.fileno()
        if fd == -1:
            for fd, fdes in self._selectables.items():
                if selectable is fdes:
                    break
            else:
                return
        if fd in mdict:
            event = mdict.pop(fd)
            try:
                event.removeFromLoop()
            except libevent.EventError:
                pass
            if fd not in other:
                del self._selectables[fd]


    def removeReader(self, reader):
        """
        Remove a selectable for notification of data available to read.
        """
        return self._remove(reader, self._reads, self._writes)


    def removeWriter(self, writer):
        """
        Remove a selectable for notification of data available to write.
        """
        return self._remove(writer, self._writes, self._reads)


    def removeAll(self):
        """
        Remove all selectables, and return a list of them.
        """
        if self.waker is not None:
            self.removeReader(self.waker)
        result = self._selectables.values()
        events = self._reads.copy()
        events.update(self._writes)

        self._reads.clear()
        self._writes.clear()
        self._selectables.clear()

        for event in events.values():
            event.removeFromLoop()
        if self.waker is not None:
            self.addReader(self.waker)
        return result


    def getReaders(self):
        return [self._selectables[fd] for fd in self._reads]


    def getWriters(self):
        return [self._selectables[fd] for fd in self._writes]


    def _eventCallback(self, fd, events, eventObj):
        """
        Called when an event id available. Wrap L{_doReadOrWrite}.
        """
        if fd in self._selectables:
            selectable = self._selectables[fd]
            log.callWithLogger(selectable,
                    self._doReadOrWrite, fd, events, selectable)


    def _handleSignals(self):
        import signal

        evt = libevent.createSignalHandler(signal.SIGINT, self.sigInt, True)
        evt.addToLoop()

        evt = libevent.createSignalHandler(signal.SIGTERM, self.sigTerm, True)
        evt.addToLoop()

        # Catch Ctrl-Break in windows
        if hasattr(signal, "SIGBREAK"):
            evt = libevent.createSignalHandler(signal.SIGBREAK, self.sigBreak,
                                               True)
            evt.addToLoop()
        if platformType == "posix":
            # Install a dummy SIGCHLD handler, to shut up warning. We could
            # install the normal handler, but it would lead to unnecessary reap
            # calls
            signal.signal(signal.SIGCHLD, lambda *args: None)
            evt = libevent.createSignalHandler(signal.SIGCHLD,
                                               self._handleSigchld, True)
            evt.addToLoop()


    def _doReadOrWrite(self, fd, events, selectable):
        """
        C{fd} is available for read or write, make the work and raise errors
        if necessary.
        """
        why = None
        inRead = False
        try:
            if events & libevent.EV_READ:
                why = selectable.doRead()
                inRead = True
            if not why and events & libevent.EV_WRITE:
                why = selectable.doWrite()
                inRead = False
            if selectable.fileno() != fd:
                why = error.ConnectionFdescWentAway('Filedescriptor went away')
                inRead = False
        except:
            log.err()
            why = sys.exc_info()[1]
        if why:
            self._disconnectSelectable(selectable, why, inRead)


    def doIteration(self, timeout):
        """
        Call one iteration of the libevent loop.
        """
        if timeout is not None:
            evt = libevent.createTimer(lambda *args: None, persist=False)
            evt.addToLoop(float(timeout))
        libevent.loop(libevent.EVLOOP_ONCE)



def install():
    """
    Install the libevent reactor.
    """
    p = LibEventReactor()
    main.installReactor(p)



__all__ = ["LibEventReactor", "install"]

