# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUNIX}.
"""

from stat import S_IMODE
from os import stat, close
from tempfile import mktemp
from socket import AF_INET, SOCK_STREAM, socket
from pprint import pformat

try:
    from socket import AF_UNIX
except ImportError:
    AF_UNIX = None

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.python.log import addObserver, removeObserver, err
from twisted.python.failure import Failure
from twisted.python.hashlib import md5
from twisted.python.runtime import platform
from twisted.internet.interfaces import (
    IConnector, IFileDescriptorReceiver, IReactorUNIX)
from twisted.internet.error import ConnectionClosed, FileDescriptorOverrun
from twisted.internet.address import UNIXAddress
from twisted.internet.endpoints import UNIXServerEndpoint, UNIXClientEndpoint
from twisted.internet.defer import Deferred, fail
from twisted.internet.task import LoopingCall
from twisted.internet import interfaces
from twisted.internet.protocol import (
    ServerFactory, ClientFactory, DatagramProtocol)
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.test.test_core import ObjectModelIntegrationMixin
from twisted.internet.test.test_tcp import StreamTransportTestsMixin
from twisted.internet.test.connectionmixins import (
    EndpointCreator, ConnectableProtocol, runProtocolsWithReactor,
    ConnectionTestsMixin)

try:
    from twisted.python import sendmsg
except ImportError:
    sendmsgSkip = (
        "sendmsg extension unavailable, extended UNIX features disabled")
else:
    sendmsgSkip = None


class UNIXFamilyMixin:
    """
    Test-helper defining mixin for things related to AF_UNIX sockets.
    """
    def _modeTest(self, methodName, path, factory):
        """
        Assert that the mode of the created unix socket is set to the mode
        specified to the reactor method.
        """
        mode = 0600
        reactor = self.buildReactor()
        unixPort = getattr(reactor, methodName)(path, factory, mode=mode)
        unixPort.stopListening()
        self.assertEqual(S_IMODE(stat(path).st_mode), mode)


def _abstractPath(case):
    """
    Return a new, unique abstract namespace path to be listened on.
    """
    # Use the test cases's mktemp to get something unique, but also squash it
    # down to make sure it fits in the unix socket path limit (something around
    # 110 bytes).
    return md5(case.mktemp()).hexdigest()



class UNIXCreator(EndpointCreator):
    """
    Create UNIX socket end points.
    """
    requiredInterfaces = (interfaces.IReactorUNIX,)

    def server(self, reactor):
        """
        Construct a UNIX server endpoint.
        """
        # self.mktemp() often returns a path which is too long to be used.
        path = mktemp(suffix='.sock', dir='.')
        return UNIXServerEndpoint(reactor, path)


    def client(self, reactor, serverAddress):
        """
        Construct a UNIX client endpoint.
        """
        return UNIXClientEndpoint(reactor, serverAddress.name)



class SendFileDescriptor(ConnectableProtocol):
    """
    L{SendFileDescriptorAndBytes} sends a file descriptor and optionally some
    normal bytes and then closes its connection.

    @ivar reason: The reason the connection was lost, after C{connectionLost}
        is called.
    """
    reason = None

    def __init__(self, fd, data):
        """
        @param fd: A C{int} giving a file descriptor to send over the
            connection.

        @param data: A C{str} giving data to send over the connection, or
            C{None} if no data is to be sent.
        """
        self.fd = fd
        self.data = data


    def connectionMade(self):
        """
        Send C{self.fd} and, if it is not C{None}, C{self.data}.  Then close the
        connection.
        """
        self.transport.sendFileDescriptor(self.fd)
        if self.data:
            self.transport.write(self.data)
        self.transport.loseConnection()


    def connectionLost(self, reason):
        ConnectableProtocol.connectionLost(self, reason)
        self.reason = reason



class ReceiveFileDescriptor(ConnectableProtocol):
    """
    L{ReceiveFileDescriptor} provides an API for waiting for file descriptors to
    be received.

    @ivar reason: The reason the connection was lost, after C{connectionLost}
        is called.

    @ivar waiting: A L{Deferred} which fires with a file descriptor once one is
        received, or with a failure if the connection is lost with no descriptor
        arriving.
    """
    implements(IFileDescriptorReceiver)

    reason = None
    waiting = None

    def waitForDescriptor(self):
        """
        Return a L{Deferred} which will fire with the next file descriptor
        received, or with a failure if the connection is or has already been
        lost.
        """
        if self.reason is None:
            self.waiting = Deferred()
            return self.waiting
        else:
            return fail(self.reason)


    def fileDescriptorReceived(self, descriptor):
        """
        Fire the waiting Deferred, initialized by C{waitForDescriptor}, with the
        file descriptor just received.
        """
        self.waiting.callback(descriptor)
        self.waiting = None


    def dataReceived(self, data):
        """
        Fail the waiting Deferred, if it has not already been fired by
        C{fileDescriptorReceived}.  The bytes sent along with a file descriptor
        are guaranteed to be delivered to the protocol's C{dataReceived} method
        only after the file descriptor has been delivered to the protocol's
        C{fileDescriptorReceived}.
        """
        if self.waiting is not None:
            self.waiting.errback(Failure(Exception(
                        "Received bytes (%r) before descriptor." % (data,))))
            self.waiting = None


    def connectionLost(self, reason):
        """
        Fail the waiting Deferred, initialized by C{waitForDescriptor}, if there
        is one.
        """
        ConnectableProtocol.connectionLost(self, reason)
        if self.waiting is not None:
            self.waiting.errback(reason)
            self.waiting = None
        self.reason = reason



class UNIXTestsBuilder(UNIXFamilyMixin, ReactorBuilder, ConnectionTestsMixin):
    """
    Builder defining tests relating to L{IReactorUNIX}.
    """
    requiredInterfaces = (IReactorUNIX,)

    endpoints = UNIXCreator()

    def test_interface(self):
        """
        L{IReactorUNIX.connectUNIX} returns an object providing L{IConnector}.
        """
        reactor = self.buildReactor()
        connector = reactor.connectUNIX(self.mktemp(), ClientFactory())
        self.assertTrue(verifyObject(IConnector, connector))


    def test_mode(self):
        """
        The UNIX socket created by L{IReactorUNIX.listenUNIX} is created with
        the mode specified.
        """
        self._modeTest('listenUNIX', self.mktemp(), ServerFactory())


    def test_listenOnLinuxAbstractNamespace(self):
        """
        On Linux, a UNIX socket path may begin with C{'\0'} to indicate a socket
        in the abstract namespace.  L{IReactorUNIX.listenUNIX} accepts such a
        path.
        """
        # Don't listen on a path longer than the maximum allowed.
        path = _abstractPath(self)
        reactor = self.buildReactor()
        port = reactor.listenUNIX('\0' + path, ServerFactory())
        self.assertEqual(port.getHost(), UNIXAddress('\0' + path))
    if not platform.isLinux():
        test_listenOnLinuxAbstractNamespace.skip = (
            'Abstract namespace UNIX sockets only supported on Linux.')


    def test_connectToLinuxAbstractNamespace(self):
        """
        L{IReactorUNIX.connectUNIX} also accepts a Linux abstract namespace
        path.
        """
        path = _abstractPath(self)
        reactor = self.buildReactor()
        connector = reactor.connectUNIX('\0' + path, ClientFactory())
        self.assertEqual(
            connector.getDestination(), UNIXAddress('\0' + path))
    if not platform.isLinux():
        test_connectToLinuxAbstractNamespace.skip = (
            'Abstract namespace UNIX sockets only supported on Linux.')


    def test_addresses(self):
        """
        A client's transport's C{getHost} and C{getPeer} return L{UNIXAddress}
        instances which have the filesystem path of the host and peer ends of
        the connection.
        """
        class SaveAddress(ConnectableProtocol):
            def makeConnection(self, transport):
                self.addresses = dict(
                    host=transport.getHost(), peer=transport.getPeer())
                transport.loseConnection()

        server = SaveAddress()
        client = SaveAddress()

        runProtocolsWithReactor(self, server, client, self.endpoints)

        self.assertEqual(server.addresses['host'], client.addresses['peer'])
        self.assertEqual(server.addresses['peer'], client.addresses['host'])


    def test_sendFileDescriptor(self):
        """
        L{IUNIXTransport.sendFileDescriptor} accepts an integer file descriptor
        and sends a copy of it to the process reading from the connection.
        """
        from socket import fromfd

        s = socket()
        s.bind(('', 0))
        server = SendFileDescriptor(s.fileno(), "junk")

        client = ReceiveFileDescriptor()
        d = client.waitForDescriptor()
        def checkDescriptor(descriptor):
            received = fromfd(descriptor, AF_INET, SOCK_STREAM)
            # Thanks for the free dup, fromfd()
            close(descriptor)

            # If the sockets have the same local address, they're probably the
            # same.
            self.assertEqual(s.getsockname(), received.getsockname())

            # But it would be cheating for them to be identified by the same
            # file descriptor.  The point was to get a copy, as we might get if
            # there were two processes involved here.
            self.assertNotEqual(s.fileno(), received.fileno())
        d.addCallback(checkDescriptor)
        d.addErrback(err, "Sending file descriptor encountered a problem")
        d.addBoth(lambda ignored: server.transport.loseConnection())

        runProtocolsWithReactor(self, server, client, self.endpoints)
    if sendmsgSkip is not None:
        test_sendFileDescriptor.skip = sendmsgSkip


    def test_sendFileDescriptorTriggersPauseProducing(self):
        """
        If a L{IUNIXTransport.sendFileDescriptor} call fills up the send buffer,
        any registered producer is paused.
        """
        class DoesNotRead(ConnectableProtocol):
            def connectionMade(self):
                self.transport.pauseProducing()

        class SendsManyFileDescriptors(ConnectableProtocol):
            paused = False

            def connectionMade(self):
                self.socket = socket()
                self.transport.registerProducer(self, True)
                def sender():
                    self.transport.sendFileDescriptor(self.socket.fileno())
                    self.transport.write("x")
                self.task = LoopingCall(sender)
                self.task.clock = self.transport.reactor
                self.task.start(0).addErrback(err, "Send loop failure")

            def stopProducing(self):
                self._disconnect()

            def resumeProducing(self):
                self._disconnect()

            def pauseProducing(self):
                self.paused = True
                self.transport.unregisterProducer()
                self._disconnect()

            def _disconnect(self):
                self.task.stop()
                self.transport.abortConnection()
                self.other.transport.abortConnection()

        server = SendsManyFileDescriptors()
        client = DoesNotRead()
        server.other = client
        runProtocolsWithReactor(self, server, client, self.endpoints)

        self.assertTrue(
            server.paused, "sendFileDescriptor producer was not paused")
    if sendmsgSkip is not None:
        test_sendFileDescriptorTriggersPauseProducing.skip = sendmsgSkip


    def test_fileDescriptorOverrun(self):
        """
        If L{IUNIXTransport.sendFileDescriptor} is used to queue a greater
        number of file descriptors than the number of bytes sent using
        L{ITransport.write}, the connection is closed and the protocol connected
        to the transport has its C{connectionLost} method called with a failure
        wrapping L{FileDescriptorOverrun}.
        """
        cargo = socket()
        server = SendFileDescriptor(cargo.fileno(), None)

        client = ReceiveFileDescriptor()
        result = []
        d = client.waitForDescriptor()
        d.addBoth(result.append)
        d.addBoth(lambda ignored: server.transport.loseConnection())

        runProtocolsWithReactor(self, server, client, self.endpoints)

        self.assertIsInstance(result[0], Failure)
        result[0].trap(ConnectionClosed)
        self.assertIsInstance(server.reason.value, FileDescriptorOverrun)
    if sendmsgSkip is not None:
        test_fileDescriptorOverrun.skip = sendmsgSkip


    def test_avoidLeakingFileDescriptors(self):
        """
        If associated with a protocol which does not provide
        L{IFileDescriptorReceiver}, file descriptors received by the
        L{IUNIXTransport} implementation are closed and a warning is emitted.
        """
        # To verify this, establish a connection.  Send one end of the
        # connection over the IUNIXTransport implementation.  After the copy
        # should no longer exist, close the original.  If the opposite end of
        # the connection decides the connection is closed, the copy does not
        # exist.
        from socket import socketpair
        probeClient, probeServer = socketpair()

        events = []
        addObserver(events.append)
        self.addCleanup(removeObserver, events.append)

        class RecordEndpointAddresses(SendFileDescriptor):
            def connectionMade(self):
                self.hostAddress = self.transport.getHost()
                self.peerAddress = self.transport.getPeer()
                SendFileDescriptor.connectionMade(self)

        server = RecordEndpointAddresses(probeClient.fileno(), "junk")
        client = ConnectableProtocol()

        runProtocolsWithReactor(self, server, client, self.endpoints)

        # Get rid of the original reference to the socket.
        probeClient.close()

        # A non-blocking recv will return "" if the connection is closed, as
        # desired.  If the connection has not been closed, because the duplicate
        # file descriptor is still open, it will fail with EAGAIN instead.
        probeServer.setblocking(False)
        self.assertEqual("", probeServer.recv(1024))

        # This is a surprising circumstance, so it should be logged.
        format = (
            "%(protocolName)s (on %(hostAddress)r) does not "
            "provide IFileDescriptorReceiver; closing file "
            "descriptor received (from %(peerAddress)r).")
        clsName = "ConnectableProtocol"

        # Reverse host and peer, since the log event is from the client
        # perspective.
        expectedEvent = dict(hostAddress=server.peerAddress,
                             peerAddress=server.hostAddress,
                             protocolName=clsName,
                             format=format)

        for logEvent in events:
            for k, v in expectedEvent.iteritems():
                if v != logEvent.get(k):
                    break
            else:
                # No mismatches were found, stop looking at events
                break
        else:
            # No fully matching events were found, fail the test.
            self.fail(
                "Expected event (%s) not found in logged events (%s)" % (
                    expectedEvent, pformat(events,)))
    if sendmsgSkip is not None:
        test_avoidLeakingFileDescriptors.skip = sendmsgSkip


    def test_descriptorDeliveredBeforeBytes(self):
        """
        L{IUNIXTransport.sendFileDescriptor} sends file descriptors before
        L{ITransport.write} sends normal bytes.
        """
        class RecordEvents(ConnectableProtocol):
            implements(IFileDescriptorReceiver)

            def connectionMade(self):
                ConnectableProtocol.connectionMade(self)
                self.events = []

            def fileDescriptorReceived(innerSelf, descriptor):
                self.addCleanup(close, descriptor)
                innerSelf.events.append(type(descriptor))

            def dataReceived(self, data):
                self.events.extend(data)

        cargo = socket()
        server = SendFileDescriptor(cargo.fileno(), "junk")
        client = RecordEvents()

        runProtocolsWithReactor(self, server, client, self.endpoints)

        self.assertEqual([int, "j", "u", "n", "k"], client.events)
    if sendmsgSkip is not None:
        test_descriptorDeliveredBeforeBytes.skip = sendmsgSkip



class UNIXDatagramTestsBuilder(UNIXFamilyMixin, ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorUNIXDatagram}.
    """
    requiredInterfaces = (interfaces.IReactorUNIXDatagram,)

    # There's no corresponding test_connectMode because the mode parameter to
    # connectUNIXDatagram has been completely ignored since that API was first
    # introduced.
    def test_listenMode(self):
        """
        The UNIX socket created by L{IReactorUNIXDatagram.listenUNIXDatagram}
        is created with the mode specified.
        """
        self._modeTest('listenUNIXDatagram', self.mktemp(), DatagramProtocol())


    def test_listenOnLinuxAbstractNamespace(self):
        """
        On Linux, a UNIX socket path may begin with C{'\0'} to indicate a socket
        in the abstract namespace.  L{IReactorUNIX.listenUNIXDatagram} accepts
        such a path.
        """
        path = _abstractPath(self)
        reactor = self.buildReactor()
        port = reactor.listenUNIXDatagram('\0' + path, DatagramProtocol())
        self.assertEqual(port.getHost(), UNIXAddress('\0' + path))
    if not platform.isLinux():
        test_listenOnLinuxAbstractNamespace.skip = (
            'Abstract namespace UNIX sockets only supported on Linux.')



class UNIXPortTestsBuilder(ReactorBuilder, ObjectModelIntegrationMixin,
                           StreamTransportTestsMixin):
    """
    Tests for L{IReactorUNIX.listenUnix}
    """
    requiredInterfaces = (interfaces.IReactorUNIX,)

    def getListeningPort(self, reactor, factory):
        """
        Get a UNIX port from a reactor
        """
        # self.mktemp() often returns a path which is too long to be used.
        path = mktemp(suffix='.sock', dir='.')
        return reactor.listenUNIX(path, factory)


    def getExpectedStartListeningLogMessage(self, port, factory):
        """
        Get the message expected to be logged when a UNIX port starts listening.
        """
        return "%s starting on %r" % (factory, port.getHost().name)


    def getExpectedConnectionLostLogMsg(self, port):
        """
        Get the expected connection lost message for a UNIX port
        """
        return "(UNIX Port %s Closed)" % (repr(port.port),)



globals().update(UNIXTestsBuilder.makeTestCaseClasses())
globals().update(UNIXDatagramTestsBuilder.makeTestCaseClasses())
globals().update(UNIXPortTestsBuilder.makeTestCaseClasses())
