# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.posixbase} and supporting code.
"""

from twisted.python.compat import set
from twisted.trial.unittest import TestCase
from twisted.internet.posixbase import PosixReactorBase, _Waker
from twisted.internet.protocol import ServerFactory
from twisted.internet.tcp import Port
from twisted.internet import reactor


class TrivialReactor(PosixReactorBase):
    def __init__(self):
        self._readers = {}
        self._writers = {}
        PosixReactorBase.__init__(self)


    def addReader(self, reader):
        self._readers[reader] = True


    def removeReader(self, reader):
        del self._readers[reader]


    def addWriter(self, writer):
        self._writers[writer] = True


    def removeWriter(self, writer):
        del self._writers[writer]



class PosixReactorBaseTests(TestCase):
    """
    Tests for L{PosixReactorBase}.
    """

    def _checkWaker(self, reactor):
        self.assertIsInstance(reactor.waker, _Waker)
        self.assertIn(reactor.waker, reactor._internalReaders)
        self.assertIn(reactor.waker, reactor._readers)


    def test_wakerIsInternalReader(self):
        """
        When L{PosixReactorBase} is instantiated, it creates a waker and adds
        it to its internal readers set.
        """
        reactor = TrivialReactor()
        self._checkWaker(reactor)


    def test_removeAllSkipsInternalReaders(self):
        """
        Any L{IReadDescriptors} in L{PosixReactorBase._internalReaders} are
        left alone by L{PosixReactorBase._removeAll}.
        """
        reactor = TrivialReactor()
        extra = object()
        reactor._internalReaders.add(extra)
        reactor.addReader(extra)
        reactor._removeAll(reactor._readers, reactor._writers)
        self._checkWaker(reactor)
        self.assertIn(extra, reactor._internalReaders)
        self.assertIn(extra, reactor._readers)


    def test_removeAllReturnsRemovedDescriptors(self):
        """
        L{PosixReactorBase._removeAll} returns a list of removed
        L{IReadDescriptor} and L{IWriteDescriptor} objects.
        """
        reactor = TrivialReactor()
        reader = object()
        writer = object()
        reactor.addReader(reader)
        reactor.addWriter(writer)
        removed = reactor._removeAll(
            reactor._readers, reactor._writers)
        self.assertEqual(set(removed), set([reader, writer]))
        self.assertNotIn(reader, reactor._readers)
        self.assertNotIn(writer, reactor._writers)



class TCPPortTests(TestCase):
    """
    Tests for L{twisted.internet.tcp.Port}.
    """

    if not isinstance(reactor, PosixReactorBase):
        skip = "Non-posixbase reactor"

    def test_connectionLostFailed(self):
        """
        L{Port.stopListening} returns a L{Deferred} which errbacks if
        L{Port.connectionLost} raises an exception.
        """
        port = Port(12345, ServerFactory())
        port.connected = True
        port.connectionLost = lambda reason: 1 / 0
        return self.assertFailure(port.stopListening(), ZeroDivisionError)
