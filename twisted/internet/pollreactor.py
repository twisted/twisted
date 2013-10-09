# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A poll() based implementation of the twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added)::

    from twisted.internet import pollreactor
    pollreactor.install()
"""

from __future__ import division, absolute_import

# System imports
import errno
from select import error as SelectError, poll
from select import POLLIN, POLLOUT, POLLHUP, POLLERR, POLLNVAL

from zope.interface import implementer

# Twisted imports
from twisted.python import log
from twisted.internet import posixbase
from twisted.internet.interfaces import IReactorFDSet



@implementer(IReactorFDSet)
class PollReactor(posixbase.PosixReactorBase, posixbase._PollLikeMixin):
    """
    A reactor that uses poll(2).

    @ivar _poller: A L{poll} which will be used to check for I/O
        readiness.

    @ivar _selectables: A dictionary mapping integer file descriptors to
        instances of L{FileDescriptor} which have been registered with the
        reactor.  All L{FileDescriptors} which are currently receiving read or
        write readiness notifications will be present as values in this
        dictionary.
    """

    _POLL_DISCONNECTED = (POLLHUP | POLLERR | POLLNVAL)
    _POLL_IN = POLLIN
    _POLL_OUT = POLLOUT

    def __init__(self):
        """
        Initialize polling object, file descriptor tracking dictionaries, and
        the base class.
        """
        self._poller = poll()
        self._selectables = {}
        posixbase.PosixReactorBase.__init__(self)


    def _updateRegistration(self, fdesc, fd):
        """Register/unregister an fd with the poller."""
        try:
            self._poller.unregister(fd)
        except KeyError:
            pass

        mask = 0
        if fdesc._isReading:
            mask |= POLLIN
        if fdesc._isWriting:
            mask |= POLLOUT
        if mask != 0:
            self._poller.register(fd, mask)
        else:
            if fd in self._selectables:
                del self._selectables[fd]

    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read.
        """
        fd = reader.fileno()
        if not reader._isReading:
            self._selectables[fd] = reader
            reader._isReading = True
            self._updateRegistration(reader, fd)

    def addWriter(self, writer):
        """Add a FileDescriptor for notification of data available to write.
        """
        fd = writer.fileno()
        if not writer._isWriting:
            self._selectables[fd] = writer
            writer._isWriting = True
            self._updateRegistration(writer, fd)


    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        fd = reader.fileno()
        if reader._isReading:
            reader._isReading = False
            self._updateRegistration(reader, fd)


    def removeWriter(self, writer):
        """Remove a Selectable for notification of data available to write.
        """
        fd = writer.fileno()
        if writer._isWriting:
            writer._isWriting = False
            self._updateRegistration(writer, fd)

    def removeAll(self):
        """
        Remove all selectables, and return a list of them.
        """
        return self._removeAll(
            self.getReaders(),
            self.getWriters()
        )


    def doPoll(self, timeout):
        """Poll the poller for new events."""
        if timeout is not None:
            timeout = int(timeout * 1000) # convert seconds to milliseconds

        try:
            l = self._poller.poll(timeout)
        except SelectError as e:
            if e.args[0] == errno.EINTR:
                return
            else:
                raise
        _drdw = self._doReadOrWrite
        for fd, event in l:
            try:
                selectable = self._selectables[fd]
            except KeyError:
                # Handles the infrequent case where one selectable's
                # handler disconnects another.
                continue
            log.callWithLogger(selectable, _drdw, selectable, fd, event)

    doIteration = doPoll

    def getReaders(self):
        return [fdes for fdes in self._selectables.itervalues() if fdes._isReading]


    def getWriters(self):
        return [fdes for fdes in self._selectables.itervalues() if fdes._isWriting]



def install():
    """Install the poll() reactor."""
    p = PollReactor()
    from twisted.internet.main import installReactor
    installReactor(p)


__all__ = ["PollReactor", "install"]
