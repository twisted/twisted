# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorFDSet}.
"""

__metaclass__ = type

import socket

from twisted.internet.interfaces import IReactorFDSet
from twisted.internet.abstract import FileDescriptor
from twisted.internet.test.reactormixins import ReactorBuilder

# twisted.internet.tcp nicely defines some names with proper values on
# several different platforms.
from twisted.internet.tcp import EINPROGRESS, EWOULDBLOCK


class ReactorFDSetTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorFDSet}.
    """
    requiredInterfaces = [IReactorFDSet]

    def _connectedPair(self):
        """
        Return the two sockets which make up a new TCP connection.
        """
        serverSocket = socket.socket()
        serverSocket.bind(('127.0.0.1', 0))
        serverSocket.listen(1)
        self.addCleanup(serverSocket.close)

        client = socket.socket()
        self.addCleanup(client.close)
        client.setblocking(False)
        try:
            client.connect(('127.0.0.1', serverSocket.getsockname()[1]))
        except socket.error, e:
            self.assertIn(e.args[0], (EINPROGRESS, EWOULDBLOCK))
        except Exception, e:
            self.fail("Connect should have succeeded or raised EINPROGRESS or EWOULDBLOCK")
        server, addr = serverSocket.accept()
        self.addCleanup(server.close)

        return client, server


    def _simpleSetup(self):
        reactor = self.buildReactor()

        client, server = self._connectedPair()

        fd = FileDescriptor(reactor)
        fd.fileno = client.fileno

        return reactor, fd, server


    def test_addReader(self):
        """
        C{reactor.addReader()} accepts an L{IReadDescriptor} provider and calls
        its C{doRead} method when there may be data available on its C{fileno}.
        """
        reactor, fd, server = self._simpleSetup()

        def removeAndStop():
            reactor.removeReader(fd)
            reactor.stop()
        fd.doRead = removeAndStop
        reactor.addReader(fd)
        server.sendall('x')

        # The reactor will only stop if it calls fd.doRead.
        self.runReactor(reactor)
        # Nothing to assert, just be glad we got this far.


    def test_removeReader(self):
        """
        L{reactor.removeReader()} accepts an L{IReadDescriptor} provider
        previously passed to C{reactor.addReader()} and causes it to no longer
        be monitored for input events.
        """
        reactor, fd, server = self._simpleSetup()

        def fail():
            self.fail("doRead should not be called")
        fd.doRead = fail

        reactor.addReader(fd)
        reactor.removeReader(fd)
        server.sendall('x')

        # Give the reactor two timed event passes to notice that there's I/O
        # (if it is incorrectly watching for I/O).
        reactor.callLater(0, reactor.callLater, 0, reactor.stop)

        self.runReactor(reactor)
        # Getting here means the right thing happened probably.


    def test_addWriter(self):
        """
        C{reactor.addWriter()} accepts an L{IWriteDescriptor} provider and
        calls its C{doWrite} method when it may be possible to write to its
        C{fileno}.
        """
        reactor, fd, server = self._simpleSetup()

        def removeAndStop():
            reactor.removeWriter(fd)
            reactor.stop()
        fd.doWrite = removeAndStop
        reactor.addWriter(fd)

        self.runReactor(reactor)
        # Getting here is great.


    def _getFDTest(self, kind):
        """
        Helper for getReaders and getWriters tests.
        """
        reactor = self.buildReactor()
        get = getattr(reactor, 'get' + kind + 's')
        add = getattr(reactor, 'add' + kind)
        remove = getattr(reactor, 'remove' + kind)

        client, server = self._connectedPair()

        self.assertNotIn(client, get())
        self.assertNotIn(server, get())

        add(client)
        self.assertIn(client, get())
        self.assertNotIn(server, get())

        remove(client)
        self.assertNotIn(client, get())
        self.assertNotIn(server, get())


    def test_getReaders(self):
        """
        L{IReactorFDSet.getReaders} reflects the additions and removals made
        with L{IReactorFDSet.addReader} and L{IReactorFDSet.removeReader}.
        """
        self._getFDTest('Reader')


    def test_removeWriter(self):
        """
        L{reactor.removeWriter()} accepts an L{IWriteDescriptor} provider
        previously passed to C{reactor.addWriter()} and causes it to no longer
        be monitored for outputability.
        """
        reactor, fd, server = self._simpleSetup()

        def fail():
            self.fail("doWrite should not be called")
        fd.doWrite = fail

        reactor.addWriter(fd)
        reactor.removeWriter(fd)

        # Give the reactor two timed event passes to notice that there's I/O
        # (if it is incorrectly watching for I/O).
        reactor.callLater(0, reactor.callLater, 0, reactor.stop)

        self.runReactor(reactor)
        # Getting here means the right thing happened probably.


    def test_getWriters(self):
        """
        L{IReactorFDSet.getWriters} reflects the additions and removals made
        with L{IReactorFDSet.addWriter} and L{IReactorFDSet.removeWriter}.
        """
        self._getFDTest('Writer')


    def test_removeAll(self):
        """
        C{reactor.removeAll()} removes all registered L{IReadDescriptor}
        providers and all registered L{IWriteDescriptor} providers and returns
        them.
        """
        reactor = self.buildReactor()

        reactor, fd, server = self._simpleSetup()

        fd.doRead = lambda: self.fail("doRead should not be called")
        fd.doWrite = lambda: self.fail("doWrite should not be called")

        server.sendall('x')

        reactor.addReader(fd)
        reactor.addWriter(fd)

        removed = reactor.removeAll()

        # Give the reactor two timed event passes to notice that there's I/O
        # (if it is incorrectly watching for I/O).
        reactor.callLater(0, reactor.callLater, 0, reactor.stop)

        self.runReactor(reactor)
        # Getting here means the right thing happened probably.

        self.assertEqual(removed, [fd])


globals().update(ReactorFDSetTestsBuilder.makeTestCaseClasses())
