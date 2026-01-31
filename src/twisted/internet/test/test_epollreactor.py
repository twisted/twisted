# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.epollreactor}.
"""

from __future__ import annotations

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


class FakeEpoll:
    """
    A fake epoll object that raises configurable errors on modify() to simulate
    fd reuse race conditions and other error scenarios.
    """

    modifyErrno: int = errno.ENOENT

    def __init__(self, size: int | None = None) -> None:
        self._registered: set[int] = set()

    def register(self, fd: int, events: int) -> None:
        self._registered.add(fd)

    def modify(self, fd: int, events: int) -> None:
        raise OSError(self.modifyErrno, "Fake error")

    def unregister(self, fd: int) -> None:
        self._registered.discard(fd)

    def poll(self, timeout: float, maxevents: int) -> list[tuple[int, int]]:
        return []

    def close(self) -> None:
        pass


class FakeEpollTests(TestCase):
    """
    Tests for L{FakeEpoll} to verify the test double behaves correctly.
    """

    def test_fakeEpoll(self) -> None:
        """
        L{FakeEpoll} tracks registered fds and raises ENOENT on modify by default.
        """
        fake = FakeEpoll()
        fake.register(5, 0)
        self.assertIn(5, fake._registered)
        fake.unregister(5)
        self.assertNotIn(5, fake._registered)
        self.assertEqual(fake.poll(1.0, 10), [])
        fake.close()
        with self.assertRaises(OSError) as cm:
            fake.modify(5, 0)
        self.assertEqual(cm.exception.errno, errno.ENOENT)


class ENOENTDescriptor:
    """
    A descriptor that tracks connectionLost calls for ENOENT testing.
    """

    def __init__(self, fd: int) -> None:
        self._fd = fd
        self.events: list[str] = []

    def fileno(self) -> int:
        return self._fd

    def logPrefix(self) -> str:
        return "ENOENTDescriptor"

    def connectionLost(self, reason: BaseException) -> None:
        from twisted.internet.error import ConnectionLost

        assert isinstance(reason, ConnectionLost)
        self.events.append("lost")


@skipIf(not epollreactor, "epoll not supported in this environment.")
class EPollENOENTTests(TestCase):
    """
    Tests for ENOENT handling in L{EPollReactor}.

    These tests verify that the reactor gracefully handles ENOENT errors
    from epoll_ctl(EPOLL_CTL_MOD), which can occur due to fd reuse race
    conditions.
    """

    def setUp(self):
        """
        Create an EPollReactor with a fake epoll that raises ENOENT on modify().
        """
        self.reactor = epollreactor.EPollReactor(poller=FakeEpoll())

    def test_addReader_ENOENT_handlesGracefully(self) -> None:
        """
        When L{EPollReactor.addReader} encounters ENOENT from
        epoll_ctl(EPOLL_CTL_MOD), it cleans up stale state and calls
        connectionLost on the old selectable. Unexpected errors are re-raised.
        """
        fd = 42
        old_descriptor = ENOENTDescriptor(fd)
        new_descriptor = ENOENTDescriptor(fd)

        # Simulate stale state from an old connection: fd is in _writes
        # and _selectables still maps to the old descriptor.
        self.reactor._writes.add(fd)
        self.reactor._selectables[fd] = old_descriptor

        # New connection tries addReader on the same fd, triggering ENOENT
        self.reactor.addReader(new_descriptor)

        self.assertIn("lost", old_descriptor.events)
        self.assertEqual(new_descriptor.events, [])

        # Verify unexpected errors are re-raised
        self.reactor._poller.modifyErrno = errno.EBADF
        self.reactor._writes.add(fd)
        with self.assertRaises(OSError) as cm:
            self.reactor.addReader(ENOENTDescriptor(fd))
        self.assertEqual(cm.exception.errno, errno.EBADF)

    def test_addWriter_ENOENT_handlesGracefully(self) -> None:
        """
        When L{EPollReactor.addWriter} encounters ENOENT from
        epoll_ctl(EPOLL_CTL_MOD), it cleans up stale state and calls
        connectionLost on the old selectable. Unexpected errors are re-raised.
        """
        fd = 42
        old_descriptor = ENOENTDescriptor(fd)
        new_descriptor = ENOENTDescriptor(fd)

        # Simulate stale state from an old connection: fd is in _reads
        # and _selectables still maps to the old descriptor.
        self.reactor._reads.add(fd)
        self.reactor._selectables[fd] = old_descriptor

        # New connection tries addWriter on the same fd, triggering ENOENT
        self.reactor.addWriter(new_descriptor)

        self.assertIn("lost", old_descriptor.events)
        self.assertEqual(new_descriptor.events, [])

        # Verify unexpected errors are re-raised
        self.reactor._poller.modifyErrno = errno.EBADF
        self.reactor._reads.add(fd)
        with self.assertRaises(OSError) as cm:
            self.reactor.addWriter(ENOENTDescriptor(fd))
        self.assertEqual(cm.exception.errno, errno.EBADF)


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
