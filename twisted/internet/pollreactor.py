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
listeners or connectors are added)::

    from twisted.internet import pollreactor
    pollreactor.install()

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System imports
import select, errno, sys

# Twisted imports
from twisted.python import log, threadable, failure
from twisted.internet import main, default, error

# globals
reads = {}
writes = {}
selectables = {}
poller = select.poll()

POLL_DISCONNECTED = (select.POLLHUP | select.POLLERR | select.POLLNVAL)


class PollReactor(default.PosixReactorBase):
    """A reactor that uses poll(2)."""

    def _updateRegistration(self, fd):
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

    def _dictRemove(self, selectable, mdict):
        try:
            # the easy way
            fd = reader.fileno()
        except:
            # the hard way: necessary because fileno() may disappear at any
            # moment, thanks to python's underlying sockets impl
            for fd, fdes in selectables.items():
                if selectable is fdes:
                    break
            else:
                # Hmm, maybe not the right course of action?  This method can't
                # fail, because it happens inside error detection...
                return
        if mdict.has_key(fd):
            del mdict[fd]
            self._updateRegistration(fd)

    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read.
        """
        fd = reader.fileno()
        if not reads.has_key(fd):
            selectables[fd] = reader
            reads[fd] =  1
            self._updateRegistration(fd)

    def addWriter(self, writer, writes=writes, selectables=selectables):
        """Add a FileDescriptor for notification of data available to write.
        """
        fd = writer.fileno()
        if not writes.has_key(fd):
            selectables[fd] = writer
            writes[fd] =  1
            self._updateRegistration(fd)

    def removeReader(self, reader, reads=reads):
        """Remove a Selectable for notification of data available to read.
        """
        return self._dictRemove(reader, reads)

    def removeWriter(self, writer, writes=writes):
        """Remove a Selectable for notification of data available to write.
        """
        return self._dictRemove(writer, writes)

    def removeAll(self, reads=reads, writes=writes, selectables=selectables):
        """Remove all selectables, and return a list of them."""
        result = selectables.values()
        fds = selectables.keys()
        reads.clear()
        writes.clear()
        selectables.clear()
        for fd in fds:
            poller.unregister(fd)
        return result

    def doPoll(self, timeout,
               reads=reads,
               writes=writes,
               selectables=selectables,
               select=select,
               log=log,
               POLLIN=select.POLLIN,
               POLLOUT=select.POLLOUT):
        """Poll the poller for new events."""
        if timeout is None:
            timeout = 1000
        else:
            timeout = int(timeout * 1000) # convert seconds to milliseconds

        try:
            l = poller.poll(timeout)
        except select.error, e:
            if e[0] == errno.EINTR:
                return
            else:
                raise
        _drdw = self._doReadOrWrite
        for fd, event in l:
            selectable = selectables[fd]
            log.callWithLogger(selectable, _drdw, selectable, fd, event, POLLIN, POLLOUT, log)

    doIteration = doPoll

    def _doReadOrWrite(self, selectable, fd, event, POLLIN, POLLOUT, log, 
        faildict={
            error.ConnectionDone: failure.Failure(error.ConnectionDone()),
            error.ConnectionLost: failure.Failure(error.ConnectionLost())
        }):
        why = None
        if event & POLL_DISCONNECTED and not (event & POLLIN):
            why = main.CONNECTION_LOST
        else:
            try:
                if event & POLLIN:
                    why = selectable.doRead()
                if not why and event & POLLOUT:
                    why = selectable.doWrite()
                if not selectable.fileno() == fd:
                    why = main.ConnectionFdescWentAway('Filedescriptor went away')
            except:
                log.deferr()
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
    p = PollReactor()
    import main
    main.installReactor(p)


__all__ = ["PollReactor", "install"]
