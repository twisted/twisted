# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""An epoll() based implementation of the twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added)::

    from twisted.internet import epollreactor
    epollreactor.install()

API Stability: stable

Maintainer: U{Jp Calderone <mailto:exarkun@twistedmatrix.com>}
"""

# System imports
import select, errno, sys

# Twisted imports
from twisted.python import _epoll
from twisted.python import log, threadable, failure
from twisted.internet import main, default, error

# globals
reads = {}
writes = {}
selectables = {}
poller = _epoll.epoll(1024)

POLL_DISCONNECTED = (_epoll.HUP | _epoll.ERR)

class EPollReactor(default.PosixReactorBase):
    """A reactor that uses epoll(4)."""

    def _add(self, xer, primary, other, selectables, dir, antidir):
        fd = xer.fileno()
        if fd not in primary:
            cmd = _epoll.CTL_ADD
            flags = dir
            if fd in other:
                flags |= antidir
                cmd = _epoll.CTL_MOD
            primary[fd] = 1
            selectables[fd] = xer
            poller.control(cmd, fd, flags)

    def addReader(self, reader, reads=reads, writes=writes, selectables=selectables):
        """Add a FileDescriptor for notification of data available to read.
        """
        self._add(reader, reads, writes, selectables, _epoll.IN, _epoll.OUT)

    def addWriter(self, writer, writes=writes, reads=reads, selectables=selectables):
        """Add a FileDescriptor for notification of data available to write.
        """
        self._add(writer, writes, reads, selectables, _epoll.OUT, _epoll.IN)

    def _remove(self, xer, primary, other, selectables, dir, antidir):
        fd = xer.fileno()
        if fd in primary:
            cmd = _epoll.CTL_DEL
            flags = dir
            if fd in other:
                flags = antidir
                cmd = _epoll.CTL_MOD
                del selectables[fd]
                del other[fd]
            del primary[fd]
            poller.control(cmd, fd, flags)

    def removeReader(self, reader, reads=reads, writes=writes, selectables=selectables):
        """Remove a Selectable for notification of data available to read.
        """
        self._remove(reader, reads, writes, selectables, _epoll.IN, _epoll.OUT)

    def removeWriter(self, writer, writes=writes, reads=reads, selectables=selectables):
        """Remove a Selectable for notification of data available to write.
        """
        self._remove(writer, writes, reads, selectables, _epoll.OUT, _epoll.IN)

    def removeAll(self, reads=reads, writes=writes, selectables=selectables):
        """Remove all selectables, and return a list of them."""
        result = selectables.values()
        fds = selectables.keys()
        reads.clear()
        writes.clear()
        selectables.clear()
        for fd in fds:
            poller.control(_epoll.CTL_DEL, fd, 0)
        return result

    def disconnectAll(self):
        try:
            return default.PosixReactorBase.disconnectAll(self)
        finally:
            poller.close()

    def doPoll(self, timeout,
               reads=reads,
               writes=writes,
               selectables=selectables,
               select=select,
               log=log):
        """Poll the poller for new events."""
        if timeout is None:
            timeout = 1000
        else:
            timeout = int(timeout * 1000) # convert seconds to milliseconds

        try:
            l = poller.wait(len(selectables), timeout)
        except select.error, e:
            if e[0] == errno.EINTR:
                return
            else:
                raise
        _drdw = self._doReadOrWrite
        for fd, event in l:
            selectable = selectables[fd]
            log.callWithLogger(selectable, _drdw, selectable, fd, event)

    doIteration = doPoll

    def _doReadOrWrite(self, selectable, fd, event,
        faildict={
            error.ConnectionDone: failure.Failure(error.ConnectionDone()),
            error.ConnectionLost: failure.Failure(error.ConnectionLost())
        }):
        why = None
        if event & _epoll.HUP:
            why = main.CONNECTION_LOST
        else:
            try:
                if event & _epoll.IN:
                    why = selectable.doRead()
                if not why and event & _epoll.OUT:
                    why = selectable.doWrite()
                if selectable.fileno() != fd:
                    why = main.ConnectionFdescWentAway('Filedescriptor went away')
            except:
                log.err()
                why = sys.exc_info()[1]
        if why:
            self.removeReader(selectable)
            self.removeWriter(selectable)
            f = faildict.get(why.__class__)
            if f:
                selectable.connectionLost(f)
            else:
                selectable.connectionLost(failure.Failure(why))


def install():
    """Install the poll() reactor."""
    p = EPollReactor()
    main.installReactor(p)


__all__ = ["PollReactor", "install"]
