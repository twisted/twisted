# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorFDSet}.
"""
from __future__ import annotations

import os
import socket
import traceback
from traceback import FrameSummary
from typing import TYPE_CHECKING, Callable
from unittest import skipIf

from zope.interface import implementer

from twisted.internet.abstract import FileDescriptor
from twisted.internet.interfaces import (
    IReactorCore,
    IReactorFDSet,
    IReactorTime,
    IReadDescriptor,
)
from twisted.internet.tcp import EINPROGRESS, EWOULDBLOCK
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.python.failure import Failure
from twisted.python.runtime import platform
from twisted.trial.unittest import FailTest, SkipTest

if TYPE_CHECKING:
    from twisted.trial.unittest import SynchronousTestCase as CheckAsTest
else:
    CheckAsTest = object


def socketpair() -> tuple[socket.socket, socket.socket]:
    serverSocket = socket.socket()
    serverSocket.bind(("127.0.0.1", 0))
    serverSocket.listen(1)
    try:
        client = socket.socket()
        try:
            client.setblocking(False)
            try:
                client.connect(("127.0.0.1", serverSocket.getsockname()[1]))
            except OSError as e:
                if e.args[0] not in (EINPROGRESS, EWOULDBLOCK):
                    raise
            server, addr = serverSocket.accept()
        except BaseException:
            client.close()
            raise
    finally:
        serverSocket.close()

    return client, server


class CustomFileDescriptor(FileDescriptor):
    def __init__(
        self,
        reactor: IReactorFDSet,
        readCallback: Callable[[], None] = lambda: None,
        writeCallback: Callable[[], None] = lambda: None,
        *,
        filenoCB: Callable[[], int],
    ) -> None:
        super().__init__(reactor)
        self.readCallback = readCallback
        self.writeCallback = writeCallback
        self.filenoCB = filenoCB

    def doRead(self) -> None:
        self.readCallback()

    def doWrite(self) -> None:
        self.writeCallback()

    def fileno(self) -> int:
        return self.filenoCB()


class ReactorFDSetTestsBuilder(ReactorBuilder, CheckAsTest):
    """
    Builder defining tests relating to L{IReactorFDSet}.
    """

    requiredInterfaces = [IReactorFDSet]

    def _connectedPair(self) -> tuple[socket.socket, socket.socket]:
        """
        Return the two sockets which make up a new TCP connection.
        """
        client, server = socketpair()
        self.addCleanup(client.close)
        self.addCleanup(server.close)
        return client, server

    def _simpleSetup(
        self,
        readCallback: Callable[[], None] = lambda: None,
        writeCallback: Callable[[], None] = lambda: None,
    ) -> tuple[IReactorFDSet, FileDescriptor, socket.socket]:
        reactor = self.buildReactor()

        client, server = self._connectedPair()

        fd = CustomFileDescriptor(
            reactor, readCallback, writeCallback, filenoCB=client.fileno
        )

        return reactor, fd, server

    def test_addReader(self) -> None:
        """
        C{reactor.addReader()} accepts an L{IReadDescriptor} provider and calls
        its C{doRead} method when there may be data available on its C{fileno}.
        """

        def removeAndStop() -> None:
            reactor.removeReader(clientfd)
            IReactorCore(reactor).stop()

        reactor, clientfd, server = self._simpleSetup(removeAndStop)
        reactor.addReader(clientfd)
        server.sendall(b"x")

        # The reactor will only stop if it calls fd.doRead.
        self.runReactor(reactor)
        # Nothing to assert, just be glad we got this far.

    def makeFailer(self, message: str) -> Callable[[], None]:
        """
        Create a callable that will fail the test with a specified message.
        """

        def fail() -> None:
            self.fail(message)

        return fail

    def test_makeFailer(self) -> None:
        """
        Ensure that the failure-test checker is called.
        """
        message = "a sample message to fail with"
        f = self.makeFailer(message)
        with self.assertRaises(FailTest) as ft:
            f()
        self.assertIn(message, str(ft.exception))

    def test_removeReader(self) -> None:
        """
        L{reactor.removeReader()} accepts an L{IReadDescriptor} provider
        previously passed to C{reactor.addReader()} and causes it to no longer
        be monitored for input events.
        """
        reactor, fd, server = self._simpleSetup(
            self.makeFailer("doRead should not be called")
        )
        reactor.addReader(fd)
        reactor.removeReader(fd)
        server.sendall(b"x")
        clock = IReactorTime(reactor)
        core = IReactorCore(reactor)

        # Give the reactor two timed event passes to notice that there's I/O
        # (if it is incorrectly watching for I/O).
        clock.callLater(0, clock.callLater, 0, core.stop)

        self.runReactor(reactor)
        # Getting here means the right thing happened probably.

    def test_addWriter(self) -> None:
        """
        C{reactor.addWriter()} accepts an L{IWriteDescriptor} provider and
        calls its C{doWrite} method when it may be possible to write to its
        C{fileno}.
        """

        def removeAndStop() -> None:
            reactor.removeWriter(fd)
            core.stop()

        reactor, fd, server = self._simpleSetup(writeCallback=removeAndStop)
        core = IReactorCore(reactor)

        reactor.addWriter(fd)

        self.runReactor(reactor)

    def _getFDTest(self, kind: str) -> None:
        """
        Helper for getReaders and getWriters tests.
        """
        reactor = self.buildReactor()
        get = getattr(reactor, "get" + kind + "s")
        add = getattr(reactor, "add" + kind)
        remove = getattr(reactor, "remove" + kind)

        client, server = self._connectedPair()

        self.assertNotIn(client, get())
        self.assertNotIn(server, get())

        add(client)
        self.assertIn(client, get())
        self.assertNotIn(server, get())

        remove(client)
        self.assertNotIn(client, get())
        self.assertNotIn(server, get())

    def test_getReaders(self) -> None:
        """
        L{IReactorFDSet.getReaders} reflects the additions and removals made
        with L{IReactorFDSet.addReader} and L{IReactorFDSet.removeReader}.
        """
        self._getFDTest("Reader")

    def test_removeWriter(self) -> None:
        """
        L{reactor.removeWriter()} accepts an L{IWriteDescriptor} provider
        previously passed to C{reactor.addWriter()} and causes it to no longer
        be monitored for outputability.
        """
        reactor, fd, server = self._simpleSetup(
            writeCallback=self.makeFailer("doWrite should not be called")
        )
        reactor.addWriter(fd)
        reactor.removeWriter(fd)
        clock = IReactorTime(reactor)
        core = IReactorCore(reactor)

        # Give the reactor two timed event passes to notice that there's I/O
        # (if it is incorrectly watching for I/O).
        clock.callLater(0, clock.callLater, 0, core.stop)

        self.runReactor(reactor)
        # Getting here means the right thing happened probably.

    def test_getWriters(self) -> None:
        """
        L{IReactorFDSet.getWriters} reflects the additions and removals made
        with L{IReactorFDSet.addWriter} and L{IReactorFDSet.removeWriter}.
        """
        self._getFDTest("Writer")

    def test_removeAll(self) -> None:
        """
        C{reactor.removeAll()} removes all registered L{IReadDescriptor}
        providers and all registered L{IWriteDescriptor} providers and returns
        them.
        """
        reactor = self.buildReactor()

        reactor, fd, server = self._simpleSetup(
            readCallback=self.makeFailer("doRead should not be called"),
            writeCallback=self.makeFailer("doWrite should not be called"),
        )

        reactor.addReader(fd)
        reactor.addWriter(fd)

        server.sendall(b"x")

        removed = reactor.removeAll()

        # Give the reactor two timed event passes to notice that there's I/O
        # (if it is incorrectly watching for I/O).
        reactor.callLater(0, reactor.callLater, 0, reactor.stop)

        self.runReactor(reactor)
        # Getting here means the right thing happened probably.

        self.assertEqual(removed, [fd])

    def test_removedFromReactor(self) -> None:
        """
        A descriptor's C{fileno} method should not be called after the
        descriptor has been removed from the reactor.
        """
        reactor = self.buildReactor()
        read, write = self._connectedPair()
        descriptor = RemovingDescriptor(reactor, read, write)
        self.assertEqual(descriptor.calls, [])
        self.assertEqual(descriptor.fileno(), read.fileno())
        self.assertEqual(len(descriptor.calls), 1)
        del descriptor.calls[:]
        reactor.callWhenRunning(descriptor.start)
        self.runReactor(reactor)
        self.assertEqual(descriptor.calls, [])

    def test_negativeOneFileDescriptor(self) -> None:
        """
        If L{FileDescriptor.fileno} returns C{-1}, the descriptor is removed
        from the reactor.
        """
        reactor = self.buildReactor()

        client, server = self._connectedPair()

        class DisappearingDescriptor(FileDescriptor):
            _fileno = server.fileno()

            _received = b""

            def fileno(self) -> int:
                return self._fileno

            def doRead(self) -> None:
                self._fileno = -1
                self._received += server.recv(1)
                client.sendall(b"y")

            def connectionLost(self, reason: Failure) -> None:
                reactor.stop()

        descriptor = DisappearingDescriptor(reactor)
        reactor.addReader(descriptor)
        client.sendall(b"x")
        self.runReactor(reactor)
        self.assertEqual(descriptor._received, b"x")

    @skipIf(platform.isWindows(), "Cannot duplicate socket filenos on Windows")
    def test_lostFileDescriptor(self) -> None:
        """
        The file descriptor underlying a FileDescriptor may be closed and
        replaced by another at some point.  Bytes which arrive on the new
        descriptor must not be delivered to the FileDescriptor which was
        originally registered with the original descriptor of the same number.

        Practically speaking, this is difficult or impossible to detect.  The
        implementation relies on C{fileno} raising an exception if the original
        descriptor has gone away.  If C{fileno} continues to return the original
        file descriptor value, the reactor may deliver events from that
        descriptor.  This is a best effort attempt to ease certain debugging
        situations.  Applications should not rely on it intentionally.
        """
        reactor = self.buildReactor()

        name = reactor.__class__.__name__
        if name in (
            "EPollReactor",
            "KQueueReactor",
            "CFReactor",
            "AsyncioSelectorReactor",
        ):
            # Closing a file descriptor immediately removes it from the epoll
            # set without generating a notification.  That means epollreactor
            # will not call any methods on Victim after the close, so there's
            # no chance to notice the socket is no longer valid.
            raise SkipTest(f"{name!r} cannot detect lost file descriptors")

        client, server = self._connectedPair()

        class Victim(CustomFileDescriptor):
            """
            This L{FileDescriptor} will have its socket closed out from under it
            and another socket will take its place.  It will raise a
            socket.error from C{fileno} after this happens (because socket
            objects remember whether they have been closed), so as long as the
            reactor calls the C{fileno} method the problem will be detected.
            """

            def connectionLost(self, reason: Failure) -> None:
                """
                When the problem is detected, the reactor should disconnect this
                file descriptor.  When that happens, stop the reactor so the
                test ends.
                """
                reactor.stop()

        reactor.addReader(
            Victim(
                reactor,
                self.makeFailer("Victim.doRead should never be called"),
                filenoCB=server.fileno,
            )
        )

        # Arrange for the socket to be replaced at some unspecified time.
        # Significantly, this will not be while any I/O processing code is on
        # the stack.  It is something that happens independently and cannot be
        # relied upon to happen at a convenient time, such as within a call to
        # doRead.
        def messItUp() -> None:
            newC, newS = self._connectedPair()
            fileno = server.fileno()
            server.close()
            os.dup2(newS.fileno(), fileno)
            newC.sendall(b"x")

        reactor.callLater(0, messItUp)

        self.runReactor(reactor)

        # If the implementation feels like logging the exception raised by
        # MessedUp.fileno, that's fine.
        self.flushLoggedErrors(socket.error)

    def test_connectionLostOnShutdown(self) -> None:
        """
        Any file descriptors added to the reactor have their C{connectionLost}
        called when C{reactor.stop} is called.
        """
        reactor = self.buildReactor()

        client, server = self._connectedPair()

        fd1 = CustomFileDescriptor(reactor, filenoCB=client.fileno)
        fd2 = CustomFileDescriptor(reactor, filenoCB=server.fileno)
        reactor.addReader(fd1)
        reactor.addWriter(fd2)

        reactor.callWhenRunning(reactor.stop)
        self.runReactor(reactor)
        self.assertTrue(fd1.disconnected)
        self.assertTrue(fd2.disconnected)


@implementer(IReadDescriptor)
class RemovingDescriptor:
    """
    A read descriptor which removes itself from the reactor as soon as it
    gets a chance to do a read and keeps track of when its own C{fileno}
    method is called.

    @ivar insideReactor: A flag which is true as long as the reactor has
        this descriptor as a reader.

    @ivar calls: A list of the bottom of the call stack for any call to
        C{fileno} when C{insideReactor} is false.
    """

    def __init__(
        self, reactor: IReactorFDSet, read: socket.socket, write: socket.socket
    ) -> None:
        self.reactor = reactor
        self.stopper = IReactorCore(reactor)
        self.insideReactor = False
        self.calls: list[list[FrameSummary]] = []
        self.read = read
        self.write = write

    def start(self) -> None:
        self.insideReactor = True
        self.reactor.addReader(self)
        self.write.sendall(b"a")

    def logPrefix(self) -> str:
        return "foo"

    def doRead(self) -> None:
        self.reactor.removeReader(self)
        self.insideReactor = False
        self.stopper.stop()
        self.read.close()
        self.write.close()

    def fileno(self) -> int:
        if not self.insideReactor:
            self.calls.append(traceback.extract_stack(limit=5)[:-1])
        return self.read.fileno()

    def connectionLost(self, reason: Failure) -> None:
        # Ideally we'd close the descriptors here... but actually
        # connectionLost is never called because we remove ourselves from the
        # reactor before it stops.
        pass


globals().update(ReactorFDSetTestsBuilder.makeTestCaseClasses())
