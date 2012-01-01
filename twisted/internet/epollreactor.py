# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An epoll() based implementation of the twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added)::

    from twisted.internet import epollreactor
    epollreactor.install()
"""

import errno

from zope.interface import implements

from twisted.internet.interfaces import IReactorFDSet

from twisted.python import log, _epoll
from twisted.internet import posixbase


class EPollReactor(posixbase.PosixReactorBase, posixbase._PollLikeMixin):
    """
    A reactor that uses epoll(4).

    @ivar _poller: A L{poll} which will be used to check for I/O
        readiness.

    @ivar _selectables: A dictionary mapping integer file descriptors to
        instances of L{FileDescriptor} which have been registered with the
        reactor.  All L{FileDescriptors} which are currently receiving read or
        write readiness notifications will be present as values in this
        dictionary.

    @ivar _reads: A dictionary mapping integer file descriptors to arbitrary
        values (this is essentially a set).  Keys in this dictionary will be
        registered with C{_poller} for read readiness notifications which will
        be dispatched to the corresponding L{FileDescriptor} instances in
        C{_selectables}.

    @ivar _writes: A dictionary mapping integer file descriptors to arbitrary
        values (this is essentially a set).  Keys in this dictionary will be
        registered with C{_poller} for write readiness notifications which will
        be dispatched to the corresponding L{FileDescriptor} instances in
        C{_selectables}.
    """
    implements(IReactorFDSet)

    # Attributes for _PollLikeMixin
    _POLL_DISCONNECTED = (_epoll.HUP | _epoll.ERR)
    _POLL_IN = _epoll.IN
    _POLL_OUT = _epoll.OUT

    def __init__(self):
        """
        Initialize epoll object, file descriptor tracking dictionaries, and the
        base class.
        """
        # Create the poller we're going to use.  The 1024 here is just a hint to
        # the kernel, it is not a hard maximum.  After Linux 2.6.8, the size
        # argument is completely ignored.
        self._poller = _epoll.epoll(1024)
        self._reads = {}
        self._writes = {}
        self._selectables = {}
        posixbase.PosixReactorBase.__init__(self)


    def _add(self, xer, primary, other, selectables, event, antievent):
        """
        Private method for adding a descriptor from the event loop.

        It takes care of adding it if  new or modifying it if already added
        for another state (read -> read/write for example).
        """
        fd = xer.fileno()
        if fd not in primary:
            cmd = _epoll.CTL_ADD
            flags = event
            if fd in other:
                flags |= antievent
                cmd = _epoll.CTL_MOD
            # epoll_ctl can raise all kinds of IOErrors, and every one
            # indicates a bug either in the reactor or application-code.
            # Let them all through so someone sees a traceback and fixes
            # something.  We'll do the same thing for every other call to
            # this method in this file.
            self._poller._control(cmd, fd, flags)

            # Update our own tracking state *only* after the epoll call has
            # succeeded.  Otherwise we may get out of sync.
            primary[fd] = 1
            selectables[fd] = xer


    def addReader(self, reader):
        """
        Add a FileDescriptor for notification of data available to read.
        """
        self._add(reader, self._reads, self._writes, self._selectables, _epoll.IN, _epoll.OUT)


    def addWriter(self, writer):
        """
        Add a FileDescriptor for notification of data available to write.
        """
        self._add(writer, self._writes, self._reads, self._selectables, _epoll.OUT, _epoll.IN)


    def _remove(self, xer, primary, other, selectables, event, antievent):
        """
        Private method for removing a descriptor from the event loop.

        It does the inverse job of _add, and also add a check in case of the fd
        has gone away.
        """
        fd = xer.fileno()
        if fd == -1:
            for fd, fdes in selectables.items():
                if xer is fdes:
                    break
            else:
                return
        if fd in primary:
            cmd = _epoll.CTL_DEL
            flags = event
            if fd in other:
                flags = antievent
                cmd = _epoll.CTL_MOD
            else:
                del selectables[fd]
            del primary[fd]
            # See comment above _control call in _add.
            self._poller._control(cmd, fd, flags)


    def removeReader(self, reader):
        """
        Remove a Selectable for notification of data available to read.
        """
        self._remove(reader, self._reads, self._writes, self._selectables, _epoll.IN, _epoll.OUT)


    def removeWriter(self, writer):
        """
        Remove a Selectable for notification of data available to write.
        """
        self._remove(writer, self._writes, self._reads, self._selectables, _epoll.OUT, _epoll.IN)

    def removeAll(self):
        """
        Remove all selectables, and return a list of them.
        """
        return self._removeAll(
            [self._selectables[fd] for fd in self._reads],
            [self._selectables[fd] for fd in self._writes])


    def getReaders(self):
        return [self._selectables[fd] for fd in self._reads]


    def getWriters(self):
        return [self._selectables[fd] for fd in self._writes]


    def doPoll(self, timeout):
        """
        Poll the poller for new events.
        """
        if timeout is None:
            timeout = 1
        timeout = int(timeout * 1000) # convert seconds to milliseconds

        try:
            # Limit the number of events to the number of io objects we're
            # currently tracking (because that's maybe a good heuristic) and
            # the amount of time we block to the value specified by our
            # caller.
            l = self._poller.wait(len(self._selectables), timeout)
        except IOError, err:
            if err.errno == errno.EINTR:
                return
            # See epoll_wait(2) for documentation on the other conditions
            # under which this can fail.  They can only be due to a serious
            # programming error on our part, so let's just announce them
            # loudly.
            raise

        _drdw = self._doReadOrWrite
        for fd, event in l:
            try:
                selectable = self._selectables[fd]
            except KeyError:
                pass
            else:
                log.callWithLogger(selectable, _drdw, selectable, fd, event)

    doIteration = doPoll


def install():
    """
    Install the epoll() reactor.
    """
    p = EPollReactor()
    from twisted.internet.main import installReactor
    installReactor(p)


__all__ = ["EPollReactor", "install"]

