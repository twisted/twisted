# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.epollreactor}.
"""

import errno
from unittest import skipIf

from twisted.internet.error import ConnectionDone
from twisted.internet.posixbase import _ContinuousPolling
from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase

try:
    from twisted.internet import epollreactor
except ImportError:
    epollreactor = None  # type: ignore[assignment]


class Descriptor:
    """
    Records reads and writes, as if it were a C{FileDescriptor}.
    """

    def __init__(self):
        self.events = []

    def fileno(self):
        return 1

    def doRead(self):
        self.events.append("read")

    def doWrite(self):
        self.events.append("write")

    def connectionLost(self, reason):
        reason.trap(ConnectionDone)
        self.events.append("lost")


class FakeEPoll:
    """
    Minimal epoll implementation that models registration lifetime.
    """

    def __init__(self):
        self.registrations = {}

    def register(self, fd, flags):
        self.registrations[fd] = flags

    def modify(self, fd, flags):
        if fd not in self.registrations:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")
        self.registrations[fd] = flags


@skipIf(not epollreactor, "epoll not supported in this environment.")
class EPollReactorTests(TestCase):
    """
    L{epollreactor.EPollReactor} keeps its descriptor tracking synchronized
    with epoll.
    """

    def _reactor(self):
        reactor = object.__new__(epollreactor.EPollReactor)
        reactor._poller = FakeEPoll()
        reactor._reads = set()
        reactor._writes = set()
        reactor._selectables = {}
        return reactor

    def test_reusedDescriptorInOtherSetIsRegistered(self):
        """
        A reused descriptor number tracked for a different writer is treated
        as a fresh reader registration rather than an epoll modification.
        """
        reactor = self._reactor()
        old = Descriptor()
        new = Descriptor()
        reactor._writes.add(1)
        reactor._selectables[1] = old

        reactor.addReader(new)

        self.assertEqual(reactor._poller.registrations, {1: epollreactor.EPOLLIN})
        self.assertEqual(reactor._reads, {1})
        self.assertEqual(reactor._writes, set())
        self.assertIs(reactor._selectables[1], new)

    def test_reusedDescriptorInPrimarySetIsRegistered(self):
        """
        A reused descriptor number tracked for a different reader does not
        cause registration of the new reader to be silently skipped.
        """
        reactor = self._reactor()
        old = Descriptor()
        new = Descriptor()
        reactor._reads.add(1)
        reactor._selectables[1] = old

        reactor.addReader(new)

        self.assertEqual(reactor._poller.registrations, {1: epollreactor.EPOLLIN})
        self.assertEqual(reactor._reads, {1})
        self.assertEqual(reactor._writes, set())
        self.assertIs(reactor._selectables[1], new)

    def test_sameDescriptorAddsSecondEventByModify(self):
        """
        A descriptor already registered as a writer is modified when the same
        selectable is also registered as a reader.
        """
        reactor = self._reactor()
        descriptor = Descriptor()
        reactor._poller.register(1, epollreactor.EPOLLOUT)
        reactor._writes.add(1)
        reactor._selectables[1] = descriptor

        reactor.addReader(descriptor)

        self.assertEqual(
            reactor._poller.registrations,
            {1: epollreactor.EPOLLIN | epollreactor.EPOLLOUT},
        )
        self.assertEqual(reactor._reads, {1})
        self.assertEqual(reactor._writes, {1})
        self.assertIs(reactor._selectables[1], descriptor)


@skipIf(not epollreactor, "epoll not supported in this environment.")
class ContinuousPollingTests(TestCase):
    """
    L{_ContinuousPolling} can be used to read and write from C{FileDescriptor}
    objects.
    """

    def test_addReader(self):
        """
        Adding a reader when there was previously no reader starts up a
        C{LoopingCall}.
        """
        poller = _ContinuousPolling(Clock())
        self.assertIsNone(poller._loop)
        reader = object()
        self.assertFalse(poller.isReading(reader))
        poller.addReader(reader)
        self.assertIsNotNone(poller._loop)
        self.assertTrue(poller._loop.running)
        self.assertIs(poller._loop.clock, poller._reactor)
        self.assertTrue(poller.isReading(reader))

    def test_addWriter(self):
        """
        Adding a writer when there was previously no writer starts up a
        C{LoopingCall}.
        """
        poller = _ContinuousPolling(Clock())
        self.assertIsNone(poller._loop)
        writer = object()
        self.assertFalse(poller.isWriting(writer))
        poller.addWriter(writer)
        self.assertIsNotNone(poller._loop)
        self.assertTrue(poller._loop.running)
        self.assertIs(poller._loop.clock, poller._reactor)
        self.assertTrue(poller.isWriting(writer))

    def test_removeReader(self):
        """
        Removing a reader stops the C{LoopingCall}.
        """
        poller = _ContinuousPolling(Clock())
        reader = object()
        poller.addReader(reader)
        poller.removeReader(reader)
        self.assertIsNone(poller._loop)
        self.assertEqual(poller._reactor.getDelayedCalls(), [])
        self.assertFalse(poller.isReading(reader))

    def test_removeWriter(self):
        """
        Removing a writer stops the C{LoopingCall}.
        """
        poller = _ContinuousPolling(Clock())
        writer = object()
        poller.addWriter(writer)
        poller.removeWriter(writer)
        self.assertIsNone(poller._loop)
        self.assertEqual(poller._reactor.getDelayedCalls(), [])
        self.assertFalse(poller.isWriting(writer))

    def test_removeUnknown(self):
        """
        Removing unknown readers and writers silently does nothing.
        """
        poller = _ContinuousPolling(Clock())
        poller.removeWriter(object())
        poller.removeReader(object())

    def test_multipleReadersAndWriters(self):
        """
        Adding multiple readers and writers results in a single
        C{LoopingCall}.
        """
        poller = _ContinuousPolling(Clock())
        writer = object()
        poller.addWriter(writer)
        self.assertIsNotNone(poller._loop)
        poller.addWriter(object())
        self.assertIsNotNone(poller._loop)
        poller.addReader(object())
        self.assertIsNotNone(poller._loop)
        poller.addReader(object())
        poller.removeWriter(writer)
        self.assertIsNotNone(poller._loop)
        self.assertTrue(poller._loop.running)
        self.assertEqual(len(poller._reactor.getDelayedCalls()), 1)

    def test_readerPolling(self):
        """
        Adding a reader causes its C{doRead} to be called every 1
        milliseconds.
        """
        reactor = Clock()
        poller = _ContinuousPolling(reactor)
        desc = Descriptor()
        poller.addReader(desc)
        self.assertEqual(desc.events, [])
        reactor.advance(0.00001)
        self.assertEqual(desc.events, ["read"])
        reactor.advance(0.00001)
        self.assertEqual(desc.events, ["read", "read"])
        reactor.advance(0.00001)
        self.assertEqual(desc.events, ["read", "read", "read"])

    def test_writerPolling(self):
        """
        Adding a writer causes its C{doWrite} to be called every 1
        milliseconds.
        """
        reactor = Clock()
        poller = _ContinuousPolling(reactor)
        desc = Descriptor()
        poller.addWriter(desc)
        self.assertEqual(desc.events, [])
        reactor.advance(0.001)
        self.assertEqual(desc.events, ["write"])
        reactor.advance(0.001)
        self.assertEqual(desc.events, ["write", "write"])
        reactor.advance(0.001)
        self.assertEqual(desc.events, ["write", "write", "write"])

    def test_connectionLostOnRead(self):
        """
        If a C{doRead} returns a value indicating disconnection,
        C{connectionLost} is called on it.
        """
        reactor = Clock()
        poller = _ContinuousPolling(reactor)
        desc = Descriptor()
        desc.doRead = lambda: ConnectionDone()
        poller.addReader(desc)
        self.assertEqual(desc.events, [])
        reactor.advance(0.001)
        self.assertEqual(desc.events, ["lost"])

    def test_connectionLostOnWrite(self):
        """
        If a C{doWrite} returns a value indicating disconnection,
        C{connectionLost} is called on it.
        """
        reactor = Clock()
        poller = _ContinuousPolling(reactor)
        desc = Descriptor()
        desc.doWrite = lambda: ConnectionDone()
        poller.addWriter(desc)
        self.assertEqual(desc.events, [])
        reactor.advance(0.001)
        self.assertEqual(desc.events, ["lost"])

    def test_removeAll(self):
        """
        L{_ContinuousPolling.removeAll} removes all descriptors and returns
        the readers and writers.
        """
        poller = _ContinuousPolling(Clock())
        reader = object()
        writer = object()
        both = object()
        poller.addReader(reader)
        poller.addReader(both)
        poller.addWriter(writer)
        poller.addWriter(both)
        removed = poller.removeAll()
        self.assertEqual(poller.getReaders(), [])
        self.assertEqual(poller.getWriters(), [])
        self.assertEqual(len(removed), 3)
        self.assertEqual(set(removed), {reader, writer, both})

    def test_getReaders(self):
        """
        L{_ContinuousPolling.getReaders} returns a list of the read
        descriptors.
        """
        poller = _ContinuousPolling(Clock())
        reader = object()
        poller.addReader(reader)
        self.assertIn(reader, poller.getReaders())

    def test_getWriters(self):
        """
        L{_ContinuousPolling.getWriters} returns a list of the write
        descriptors.
        """
        poller = _ContinuousPolling(Clock())
        writer = object()
        poller.addWriter(writer)
        self.assertIn(writer, poller.getWriters())
