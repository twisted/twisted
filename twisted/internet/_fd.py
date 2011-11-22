# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for generic select()able objects with explicit state machines.
"""

__metaclass__ = type

from zope.interface import implements
from twisted.python._statedispatch import makeStatefulDispatcher
from twisted.internet.interfaces import IReadWriteDescriptor
from twisted.internet.abstract import _LogOwner


class FileDescriptor(_LogOwner):
    """
    A file descriptor which can be queried by select() and similar APIs.

    All public methods should be dispatched by a state machine.

    @ivar _state: The current state of the state machine.

    @ivar _reactor: The reactor this file descriptor is connected to.
    """
    implements(IReadWriteDescriptor)

    _state = None

    def __init__(self, reactor):
        self._reactor = reactor


    def fileno(self):
        """
        Return a valid file descriptor, which the reactor will wait on.
        """
    fileno = makeStatefulDispatcher("fileno", fileno)


    def doRead(self):
        """
        Some data is available for reading on this descriptor.

        @return: If an error is encountered which causes the descriptor to
            no longer be valid, a C{Failure} should be returned.  Otherwise,
            C{None}.
        """
    doRead = makeStatefulDispatcher("doRead", doRead)


    def doWrite():
        """
        Some data can be written to this descriptor.

        @return: If an error is encountered which causes the descriptor to
            no longer be valid, a C{Failure} should be returned.  Otherwise,
            C{None}.
        """
    doWrite = makeStatefulDispatcher("doWrite", doWrite)


    def connectionLost(self, reason):
        """
        The connection was lost.

        This is called when the connection on a selectable object has been
        lost.  It will be called whether the connection was closed explicitly,
        an exception occurred in an event handler, or the other end of the
        connection closed it first.
        """
    connectionLost = makeStatefulDispatcher("connectionLost", connectionLost)


    def stopReading(self):
        """
        Stop waiting for read notification.
        """
    stopReading = makeStatefulDispatcher("stopReading", stopReading)


    def _stopReading_default(self):
        """
        Remove the file descriptor from the reactor's read set.
        """
        self._reactor.removeReader(self)


    def stopWriting(self):
        """
        Stop waiting for write notification.
        """
    stopWriting = makeStatefulDispatcher("stopWriting", stopWriting)


    def _stopWriting_default(self):
        """
        Remove the file descriptor from the reactor's write set.
        """
        self._reactor.removeWriter(self)


    def startReading(self):
        """
        Start waiting for read notification.
        """
    startReading = makeStatefulDispatcher("startReading", startReading)


    def _startReading_default(self):
        """
        Add file descriptor to reactor read set.
        """
        self._reactor.addReader(self)


    def startWriting(self):
        """
        Start waiting for write notification.
        """
    startWriting = makeStatefulDispatcher("startWriting", startWriting)


    def _startWriting_default(self):
        """
        Add file descriptor to reactor write set.
        """
        self._reactor.addWriter(self)
