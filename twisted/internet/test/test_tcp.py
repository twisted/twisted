# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorTCP}.
"""

__metaclass__ = type

import socket, errno

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.python.runtime import platform
from twisted.python.failure import Failure
from twisted.python import log

from twisted.trial.unittest import SkipTest, TestCase
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import (
    IResolverSimple, IConnector, IReactorFDSet)
from twisted.internet.address import IPv4Address
from twisted.internet.defer import (
    Deferred, DeferredList, succeed, fail, maybeDeferred, gatherResults)
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint
from twisted.internet.protocol import ServerFactory, ClientFactory, Protocol
from twisted.internet.interfaces import IPushProducer, IPullProducer
from twisted.internet.tcp import Connection, Server

from twisted.internet.test.connectionmixins import (
    ConnectionTestsMixin, serverFactoryFor)
from twisted.internet.test.test_core import ObjectModelIntegrationMixin
from twisted.test.test_tcp import MyClientFactory, MyServerFactory
from twisted.test.test_tcp import ClosingProtocol

try:
    from twisted.internet.ssl import ClientContextFactory
except ImportError:
    ClientContextFactory = None

def findFreePort(interface='127.0.0.1', type=socket.SOCK_STREAM):
    """
    Ask the platform to allocate a free port on the specified interface,
    then release the socket and return the address which was allocated.

    @param interface: The local address to try to bind the port on.
    @type interface: C{str}

    @param type: The socket type which will use the resulting port.

    @return: A two-tuple of address and port, like that returned by
        L{socket.getsockname}.
    """
    family = socket.AF_INET
    probe = socket.socket(family, type)
    try:
        probe.bind((interface, 0))
        return probe.getsockname()
    finally:
        probe.close()



class Stop(ClientFactory):
    """
    A client factory which stops a reactor when a connection attempt fails.
    """
    def __init__(self, reactor):
        self.reactor = reactor


    def clientConnectionFailed(self, connector, reason):
        self.reactor.stop()



class FakeResolver:
    """
    A resolver implementation based on a C{dict} mapping names to addresses.
    """
    implements(IResolverSimple)

    def __init__(self, names):
        self.names = names


    def getHostByName(self, name, timeout):
        try:
            return succeed(self.names[name])
        except KeyError:
            return fail(DNSLookupError("FakeResolver couldn't find " + name))



class _SimplePullProducer(object):
    """
    A pull producer which writes one byte whenever it is resumed.  For use by
    L{test_unregisterProducerAfterDisconnect}.
    """
    def __init__(self, consumer):
        self.consumer = consumer


    def stopProducing(self):
        pass


    def resumeProducing(self):
        log.msg("Producer.resumeProducing")
        self.consumer.write('x')



def _getWriters(reactor):
    """
    Like L{IReactorFDSet.getWriters}, but with support for IOCP reactor as well.
    """
    if IReactorFDSet.providedBy(reactor):
        return reactor.getWriters()
    elif 'IOCP' in reactor.__class__.__name__:
        return reactor.handles
    else:
        # Cannot tell what is going on.
        raise Exception("Cannot find writers on %r" % (reactor,))



class FakeSocket(object):
    """
    A fake for L{socket.socket} objects.

    @ivar data: A C{str} giving the data which will be returned from
        L{FakeSocket.recv}.

    @ivar sendBuffer: A C{list} of the objects passed to L{FakeSocket.send}.
    """
    def __init__(self, data):
        self.data = data
        self.sendBuffer = []

    def setblocking(self, blocking):
        self.blocking = blocking

    def recv(self, size):
        return self.data

    def send(self, bytes):
        """
        I{Send} all of C{bytes} by accumulating it into C{self.sendBuffer}.

        @return: The length of C{bytes}, indicating all the data has been
            accepted.
        """
        self.sendBuffer.append(bytes)
        return len(bytes)


    def shutdown(self, how):
        """
        Shutdown is not implemented.  The method is provided since real sockets
        have it and some code expects it.  No behavior of L{FakeSocket} is
        affected by a call to it.
        """


    def close(self):
        """
        Close is not implemented.  The method is provided since real sockets
        have it and some code expects it.  No behavior of L{FakeSocket} is
        affected by a call to it.
        """


    def fileno(self):
        """
        Return a fake file descriptor.  If actually used, this will have no
        connection to this L{FakeSocket} and will probably cause surprising
        results.
        """
        return 1



class TestFakeSocket(TestCase):
    """
    Test that the FakeSocket can be used by the doRead method of L{Connection}
    """

    def test_blocking(self):
        skt = FakeSocket("someData")
        skt.setblocking(0)
        self.assertEqual(skt.blocking, 0)


    def test_recv(self):
        skt = FakeSocket("someData")
        self.assertEqual(skt.recv(10), "someData")


    def test_send(self):
        """
        L{FakeSocket.send} accepts the entire string passed to it, adds it to
        its send buffer, and returns its length.
        """
        skt = FakeSocket("")
        count = skt.send("foo")
        self.assertEqual(count, 3)
        self.assertEqual(skt.sendBuffer, ["foo"])



class FakeProtocol(Protocol):
    """
    An L{IProtocol} that returns a value from its dataReceived method.
    """
    def dataReceived(self, data):
        """
        Return something other than C{None} to trigger a deprecation warning for
        that behavior.
        """
        return ()



class _FakeFDSetReactor(object):
    """
    A no-op implementation of L{IReactorFDSet}, which ignores all adds and
    removes.
    """
    implements(IReactorFDSet)

    addReader = addWriter = removeReader = removeWriter = (
        lambda self, desc: None)



class TCPServerTests(TestCase):
    """
    Whitebox tests for L{twisted.internet.tcp.Server}.
    """
    def setUp(self):
        self.reactor = _FakeFDSetReactor()
        class FakePort(object):
            _realPortNumber = 3
        self.skt = FakeSocket("")
        self.protocol = Protocol()
        self.server = Server(
            self.skt, self.protocol, ("", 0), FakePort(), None, self.reactor)


    def test_writeAfterDisconnect(self):
        """
        L{Server.write} discards bytes passed to it if called after it has lost
        its connection.
        """
        self.server.connectionLost(
            Failure(Exception("Simulated lost connection")))
        self.server.write("hello world")
        self.assertEqual(self.skt.sendBuffer, [])


    def test_writeAfteDisconnectAfterTLS(self):
        """
        L{Server.write} discards bytes passed to it if called after it has lost
        its connection when the connection had started TLS.
        """
        self.server.TLS = True
        self.test_writeAfterDisconnect()


    def test_writeSequenceAfterDisconnect(self):
        """
        L{Server.writeSequence} discards bytes passed to it if called after it
        has lost its connection.
        """
        self.server.connectionLost(
            Failure(Exception("Simulated lost connection")))
        self.server.writeSequence(["hello world"])
        self.assertEqual(self.skt.sendBuffer, [])


    def test_writeSequenceAfteDisconnectAfterTLS(self):
        """
        L{Server.writeSequence} discards bytes passed to it if called after it
        has lost its connection when the connection had started TLS.
        """
        self.server.TLS = True
        self.test_writeSequenceAfterDisconnect()



class TCPConnectionTests(TestCase):
    """
    Whitebox tests for L{twisted.internet.tcp.Connection}.
    """
    def test_doReadWarningIsRaised(self):
        """
        When an L{IProtocol} implementation that returns a value from its
        C{dataReceived} method, a deprecated warning is emitted.
        """
        skt = FakeSocket("someData")
        protocol = FakeProtocol()
        conn = Connection(skt, protocol)
        conn.doRead()
        warnings = self.flushWarnings([FakeProtocol.dataReceived])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]["message"],
            "Returning a value other than None from "
            "twisted.internet.test.test_tcp.FakeProtocol.dataReceived "
            "is deprecated since Twisted 11.0.0.")
        self.assertEqual(len(warnings), 1)


    def test_noTLSBeforeStartTLS(self):
        """
        The C{TLS} attribute of a L{Connection} instance is C{False} before
        L{Connection.startTLS} is called.
        """
        skt = FakeSocket("")
        protocol = FakeProtocol()
        conn = Connection(skt, protocol)
        self.assertFalse(conn.TLS)


    def test_tlsAfterStartTLS(self):
        """
        The C{TLS} attribute of a L{Connection} instance is C{True} after
        L{Connection.startTLS} is called.
        """
        skt = FakeSocket("")
        protocol = FakeProtocol()
        conn = Connection(skt, protocol, reactor=_FakeFDSetReactor())
        conn._tlsClientDefault = True
        conn.startTLS(ClientContextFactory(), True)
        self.assertTrue(conn.TLS)
    if ClientContextFactory is None:
        test_tlsAfterStartTLS.skip = "No SSL support available"


class TCPClientTestsBuilder(ReactorBuilder, ConnectionTestsMixin):
    """
    Builder defining tests relating to L{IReactorTCP.connectTCP}.
    """
    def serverEndpoint(self, reactor):
        """
        Create a L{TCP4ServerEndpoint} listening on localhost on a
        TCP/IP-selected port.
        """
        return TCP4ServerEndpoint(reactor, 0, interface='127.0.0.1')


    def clientEndpoint(self, reactor, serverAddress):
        """
        Create a L{TCP4ClientEndpoint} which will connect to localhost
        on the port given by C{serverAddress}.

        @type serverAddress: L{IPv4Address}
        """
        return TCP4ClientEndpoint(
            reactor, '127.0.0.1', serverAddress.port)


    def test_interface(self):
        """
        L{IReactorTCP.connectTCP} returns an object providing L{IConnector}.
        """
        reactor = self.buildReactor()
        connector = reactor.connectTCP("127.0.0.1", 1234, ClientFactory())
        self.assertTrue(verifyObject(IConnector, connector))


    def test_clientConnectionFailedStopsReactor(self):
        """
        The reactor can be stopped by a client factory's
        C{clientConnectionFailed} method.
        """
        host, port = findFreePort()
        reactor = self.buildReactor()
        reactor.connectTCP(host, port, Stop(reactor))
        self.runReactor(reactor)


    def test_addresses(self):
        """
        A client's transport's C{getHost} and C{getPeer} return L{IPv4Address}
        instances which give the dotted-quad string form of the local and
        remote endpoints of the connection respectively.
        """
        host, port = findFreePort()
        reactor = self.buildReactor()

        server = reactor.listenTCP(
            0, serverFactoryFor(Protocol), interface=host)
        serverAddress = server.getHost()

        addresses = {'host': None, 'peer': None}
        class CheckAddress(Protocol):
            def makeConnection(self, transport):
                addresses['host'] = transport.getHost()
                addresses['peer'] = transport.getPeer()
                reactor.stop()

        clientFactory = Stop(reactor)
        clientFactory.protocol = CheckAddress
        reactor.connectTCP(
            'localhost', server.getHost().port, clientFactory,
            bindAddress=('127.0.0.1', port))

        reactor.installResolver(FakeResolver({'localhost': '127.0.0.1'}))
        self.runReactor(reactor)

        self.assertEqual(
            addresses['host'],
            IPv4Address('TCP', '127.0.0.1', port))
        self.assertEqual(
            addresses['peer'],
            IPv4Address('TCP', '127.0.0.1', serverAddress.port))


    def test_connectEvent(self):
        """
        This test checks that we correctly get notifications event for a
        client. This ought to prevent a regression under Windows using the GTK2
        reactor. See #3925.
        """
        reactor = self.buildReactor()

        server = reactor.listenTCP(0, serverFactoryFor(Protocol))
        connected = []

        class CheckConnection(Protocol):
            def connectionMade(self):
                connected.append(self)
                reactor.stop()

        clientFactory = Stop(reactor)
        clientFactory.protocol = CheckConnection
        reactor.connectTCP(
            '127.0.0.1', server.getHost().port, clientFactory)

        reactor.run()

        self.assertTrue(connected)


    def test_unregisterProducerAfterDisconnect(self):
        """
        If a producer is unregistered from a L{ITCPTransport} provider after the
        transport has been disconnected (by the peer) and after
        L{ITCPTransport.loseConnection} has been called, the transport is not
        re-added to the reactor as a writer as would be necessary if the
        transport were still connected.
        """
        reactor = self.buildReactor()
        port = reactor.listenTCP(0, serverFactoryFor(ClosingProtocol))

        finished = Deferred()
        finished.addErrback(log.err)
        finished.addCallback(lambda ign: reactor.stop())

        writing = []

        class ClientProtocol(Protocol):
            """
            Protocol to connect, register a producer, try to lose the
            connection, wait for the server to disconnect from us, and
            then unregister the producer.
            """
            def connectionMade(self):
                log.msg("ClientProtocol.connectionMade")
                self.transport.registerProducer(
                    _SimplePullProducer(self.transport), False)
                self.transport.loseConnection()

            def connectionLost(self, reason):
                log.msg("ClientProtocol.connectionLost")
                self.unregister()
                writing.append(self.transport in _getWriters(reactor))
                finished.callback(None)

            def unregister(self):
                log.msg("ClientProtocol unregister")
                self.transport.unregisterProducer()

        clientFactory = ClientFactory()
        clientFactory.protocol = ClientProtocol
        reactor.connectTCP('127.0.0.1', port.getHost().port, clientFactory)
        self.runReactor(reactor)
        self.assertFalse(
            writing[0], "Transport was writing after unregisterProducer.")


    def test_disconnectWhileProducing(self):
        """
        If L{ITCPTransport.loseConnection} is called while a producer
        is registered with the transport, the connection is closed
        after the producer is unregistered.
        """
        reactor = self.buildReactor()

        # XXX For some reason, pyobject/pygtk will not deliver the close
        # notification that should happen after the unregisterProducer call in
        # this test.  The selectable is in the write notification set, but no
        # notification ever arrives.
        skippedReactors = ["Glib2Reactor", "Gtk2Reactor"]
        reactorClassName = reactor.__class__.__name__
        if reactorClassName in skippedReactors and platform.isWindows():
            raise SkipTest(
                "A pygobject/pygtk bug disables this functionality on Windows.")

        class Producer:
            def resumeProducing(self):
                log.msg("Producer.resumeProducing")

        port = reactor.listenTCP(0, serverFactoryFor(Protocol))

        finished = Deferred()
        finished.addErrback(log.err)
        finished.addCallback(lambda ign: reactor.stop())

        class ClientProtocol(Protocol):
            """
            Protocol to connect, register a producer, try to lose the
            connection, unregister the producer, and wait for the connection to
            actually be lost.
            """
            def connectionMade(self):
                log.msg("ClientProtocol.connectionMade")
                self.transport.registerProducer(Producer(), False)
                self.transport.loseConnection()
                # Let the reactor tick over, in case synchronously calling
                # loseConnection and then unregisterProducer is the same as
                # synchronously calling unregisterProducer and then
                # loseConnection (as it is in several reactors).
                reactor.callLater(0, reactor.callLater, 0, self.unregister)

            def unregister(self):
                log.msg("ClientProtocol unregister")
                self.transport.unregisterProducer()
                # This should all be pretty quick.  Fail the test
                # if we don't get a connectionLost event really
                # soon.
                reactor.callLater(
                    1.0, finished.errback,
                    Failure(Exception("Connection was not lost")))

            def connectionLost(self, reason):
                log.msg("ClientProtocol.connectionLost")
                finished.callback(None)

        clientFactory = ClientFactory()
        clientFactory.protocol = ClientProtocol
        reactor.connectTCP('127.0.0.1', port.getHost().port, clientFactory)
        self.runReactor(reactor)
        # If the test failed, we logged an error already and trial
        # will catch it.



class StreamTransportTestsMixin:
    """
    Mixin defining tests which apply to any port/connection based transport.
    """
    def test_connectionLostLogMsg(self):
        """
        When a connection is lost, an informative message should be logged
        (see L{getExpectedConnectionLostLogMsg}): an address identifying
        the port and the fact that it was closed.
        """

        loggedMessages = []
        def logConnectionLostMsg(eventDict):
            loggedMessages.append(log.textFromEventDict(eventDict))

        reactor = self.buildReactor()
        p = self.getListeningPort(reactor)
        expectedMessage = self.getExpectedConnectionLostLogMsg(p)
        log.addObserver(logConnectionLostMsg)

        def stopReactor(ignored):
            log.removeObserver(logConnectionLostMsg)
            reactor.stop()

        def doStopListening():
            log.addObserver(logConnectionLostMsg)
            maybeDeferred(p.stopListening).addCallback(stopReactor)

        reactor.callWhenRunning(doStopListening)
        reactor.run()

        self.assertIn(expectedMessage, loggedMessages)


    def test_allNewStyle(self):
        """
        The L{IListeningPort} object is an instance of a class with no
        classic classes in its hierarchy.
        """
        reactor = self.buildReactor()
        port = self.getListeningPort(reactor)
        self.assertFullyNewStyle(port)



class TCPPortTestsBuilder(ReactorBuilder, ObjectModelIntegrationMixin,
                          StreamTransportTestsMixin):
    """
    Tests for L{IReactorTCP.listenTCP}
    """
    def getListeningPort(self, reactor):
        """
        Get a TCP port from a reactor.
        """
        return reactor.listenTCP(0, ServerFactory())


    def getExpectedConnectionLostLogMsg(self, port):
        """
        Get the expected connection lost message for a TCP port.
        """
        return "(TCP Port %s Closed)" % (port.getHost().port,)


    def test_portGetHostOnIPv4(self):
        """
        When no interface is passed to L{IReactorTCP.listenTCP}, the returned
        listening port listens on an IPv4 address.
        """
        reactor = self.buildReactor()
        port = reactor.listenTCP(0, ServerFactory())
        address = port.getHost()
        self.assertIsInstance(address, IPv4Address)


    def _buildProtocolAddressTest(self, client, interface):
        """
        Connect C{client} to a server listening on C{interface} started with
        L{IReactorTCP.listenTCP} and return the address passed to the factory's
        C{buildProtocol} method.

        @param client: A C{SOCK_STREAM} L{socket.socket} created with an address
            family such that it will be able to connect to a server listening on
            C{interface}.

        @param interface: A C{str} giving an address for a server to listen on.
            This should almost certainly be the loopback address for some
            address family supported by L{IReactorTCP.listenTCP}.

        @return: Whatever object, probably an L{IAddress} provider, is passed to
            a server factory's C{buildProtocol} method when C{client}
            establishes a connection.
        """
        class ObserveAddress(ServerFactory):
            def buildProtocol(self, address):
                reactor.stop()
                self.observedAddress = address
                return Protocol()

        factory = ObserveAddress()
        reactor = self.buildReactor()
        port = reactor.listenTCP(0, factory, interface=interface)
        client.setblocking(False)
        try:
            client.connect((port.getHost().host, port.getHost().port))
        except socket.error, (errnum, message):
            self.assertIn(errnum, (errno.EINPROGRESS, errno.EWOULDBLOCK))

        self.runReactor(reactor)

        return factory.observedAddress


    def test_buildProtocolIPv4Address(self):
        """
        When a connection is accepted over IPv4, an L{IPv4Address} is passed
        to the factory's C{buildProtocol} method giving the peer's address.
        """
        interface = '127.0.0.1'
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        observedAddress = self._buildProtocolAddressTest(client, interface)
        self.assertEqual(
            IPv4Address('TCP', *client.getsockname()), observedAddress)


    def _serverGetConnectionAddressTest(self, client, interface, which):
        """
        Connect C{client} to a server listening on C{interface} started with
        L{IReactorTCP.listenTCP} and return the address returned by one of the
        server transport's address lookup methods, C{getHost} or C{getPeer}.

        @param client: A C{SOCK_STREAM} L{socket.socket} created with an address
            family such that it will be able to connect to a server listening on
            C{interface}.

        @param interface: A C{str} giving an address for a server to listen on.
            This should almost certainly be the loopback address for some
            address family supported by L{IReactorTCP.listenTCP}.

        @param which: A C{str} equal to either C{"getHost"} or C{"getPeer"}
            determining which address will be returned.

        @return: Whatever object, probably an L{IAddress} provider, is returned
            from the method indicated by C{which}.
        """
        class ObserveAddress(Protocol):
            def makeConnection(self, transport):
                reactor.stop()
                self.factory.address = getattr(transport, which)()

        reactor = self.buildReactor()
        factory = ServerFactory()
        factory.protocol = ObserveAddress
        port = reactor.listenTCP(0, factory, interface=interface)
        client.setblocking(False)
        try:
            client.connect((port.getHost().host, port.getHost().port))
        except socket.error, (errnum, message):
            self.assertIn(errnum, (errno.EINPROGRESS, errno.EWOULDBLOCK))
        self.runReactor(reactor)
        return factory.address


    def test_serverGetHostOnIPv4(self):
        """
        When a connection is accepted over IPv4, the server
        L{ITransport.getHost} method returns an L{IPv4Address} giving the
        address on which the server accepted the connection.
        """
        interface = '127.0.0.1'
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        hostAddress = self._serverGetConnectionAddressTest(
            client, interface, 'getHost')
        self.assertEqual(
            IPv4Address('TCP', *client.getpeername()), hostAddress)


    def test_serverGetPeerOnIPv4(self):
        """
        When a connection is accepted over IPv4, the server
        L{ITransport.getPeer} method returns an L{IPv4Address} giving the
        address of the remote end of the connection.
        """
        interface = '127.0.0.1'
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        peerAddress = self._serverGetConnectionAddressTest(
            client, interface, 'getPeer')
        self.assertEqual(
            IPv4Address('TCP', *client.getsockname()), peerAddress)



class StopStartReadingProtocol(Protocol):
    """
    Protocol that pauses and resumes the transport a few times
    """
    def connectionMade(self):
        self.data = ''
        self.pauseResumeProducing(3)


    def pauseResumeProducing(self, counter):
        """
        Toggle transport read state, then count down.
        """
        self.transport.pauseProducing()
        self.transport.resumeProducing()
        if counter:
            self.factory.reactor.callLater(0,
                    self.pauseResumeProducing, counter - 1)
        else:
            self.factory.reactor.callLater(0,
                    self.factory.ready.callback, self)


    def dataReceived(self, data):
        log.msg('got data', len(data))
        self.data += data
        if len(self.data) == 4*4096:
            self.factory.stop.callback(self.data)



class TCPConnectionTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{twisted.internet.tcp.Connection}.
    """
    def test_stopStartReading(self):
        """
        This test verifies transport socket read state after multiple
        pause/resumeProducing calls.
        """
        sf = ServerFactory()
        reactor = sf.reactor = self.buildReactor()

        skippedReactors = ["Glib2Reactor", "Gtk2Reactor"]
        reactorClassName = reactor.__class__.__name__
        if reactorClassName in skippedReactors and platform.isWindows():
            raise SkipTest(
                "This test is broken on gtk/glib under Windows.")

        sf.protocol = StopStartReadingProtocol
        sf.ready = Deferred()
        sf.stop = Deferred()
        p = reactor.listenTCP(0, sf)
        port = p.getHost().port
        def proceed(protos, port):
            """
            Send several IOCPReactor's buffers' worth of data.
            """
            self.assertTrue(protos[0])
            self.assertTrue(protos[1])
            protos = protos[0][1], protos[1][1]
            protos[0].transport.write('x' * (2 * 4096) + 'y' * (2 * 4096))
            return (sf.stop.addCallback(cleanup, protos, port)
                           .addCallback(lambda ign: reactor.stop()))

        def cleanup(data, protos, port):
            """
            Make sure IOCPReactor didn't start several WSARecv operations
            that clobbered each other's results.
            """
            self.assertEqual(data, 'x'*(2*4096) + 'y'*(2*4096),
                                 'did not get the right data')
            return DeferredList([
                    maybeDeferred(protos[0].transport.loseConnection),
                    maybeDeferred(protos[1].transport.loseConnection),
                    maybeDeferred(port.stopListening)])

        cc = TCP4ClientEndpoint(reactor, '127.0.0.1', port)
        cf = ClientFactory()
        cf.protocol = Protocol
        d = DeferredList([cc.connect(cf), sf.ready]).addCallback(proceed, p)
        self.runReactor(reactor)
        return d



class WriteSequenceTests(ReactorBuilder):
    """
    Test for L{twisted.internet.abstract.FileDescriptor.writeSequence}.

    @ivar client: the connected client factory to be used in tests.
    @type client: L{MyClientFactory}

    @ivar server: the listening server factory to be used in tests.
    @type server: L{MyServerFactory}
    """
    def setUp(self):
        server = MyServerFactory()
        server.protocolConnectionMade = Deferred()
        server.protocolConnectionLost = Deferred()
        self.server = server

        client = MyClientFactory()
        client.protocolConnectionMade = Deferred()
        client.protocolConnectionLost = Deferred()
        self.client = client


    def setWriteBufferSize(self, transport, value):
        """
        Set the write buffer size for the given transport, mananing possible
        differences (ie, IOCP). Bug #4322 should remove the need of that hack.
        """
        if getattr(transport, "writeBufferSize", None) is not None:
            transport.writeBufferSize = value
        else:
            transport.bufferSize = value


    def test_withoutWrite(self):
        """
        C{writeSequence} sends the data even if C{write} hasn't been called.
        """
        client, server = self.client, self.server
        reactor = self.buildReactor()

        port = reactor.listenTCP(0, server)
        self.addCleanup(port.stopListening)

        connector = reactor.connectTCP(
            "127.0.0.1", port.getHost().port, client)
        self.addCleanup(connector.disconnect)

        def dataReceived(data):
            log.msg("data received: %r" % data)
            self.assertEquals(data, "Some sequence splitted")
            client.protocol.transport.loseConnection()

        def clientConnected(proto):
            log.msg("client connected %s" % proto)
            proto.transport.writeSequence(["Some ", "sequence ", "splitted"])

        def serverConnected(proto):
            log.msg("server connected %s" % proto)
            proto.dataReceived = dataReceived

        d1 = client.protocolConnectionMade.addCallback(clientConnected)
        d2 = server.protocolConnectionMade.addCallback(serverConnected)
        d3 = server.protocolConnectionLost
        d4 = client.protocolConnectionLost
        d = gatherResults([d1, d2, d3, d4])
        def stop(result):
            reactor.stop()
            return result
        d.addBoth(stop)
        self.runReactor(reactor)


    def _producerTest(self, clientConnected):
        """
        Helper for testing producers which call C{writeSequence}.  This will set
        up a connection which a producer can use.  It returns after the
        connection is closed.

        @param clientConnected: A callback which will be invoked with a client
            protocol after a connection is setup.  This is responsible for
            setting up some sort of producer.
        """
        reactor = self.buildReactor()

        port = reactor.listenTCP(0, self.server)
        self.addCleanup(port.stopListening)

        connector = reactor.connectTCP(
            "127.0.0.1", port.getHost().port, self.client)
        self.addCleanup(connector.disconnect)

        # The following could probably all be much simpler, but for #5285.

        # First let the server notice the connection
        d1 = self.server.protocolConnectionMade

        # Grab the client connection Deferred now though, so we don't lose it if
        # the client connects before the server.
        d2 = self.client.protocolConnectionMade

        def serverConnected(proto):
            # Now take action as soon as the client is connected
            d2.addCallback(clientConnected)
            return d2
        d1.addCallback(serverConnected)

        d3 = self.server.protocolConnectionLost
        d4 = self.client.protocolConnectionLost

        # After the client is connected and does its producer stuff, wait for
        # the disconnection events.
        def didProducerActions(ignored):
            return gatherResults([d3, d4])
        d1.addCallback(didProducerActions)

        def stop(result):
            reactor.stop()
            return result
        d1.addBoth(stop)
        self.runReactor(reactor)


    def test_streamingProducer(self):
        """
        C{writeSequence} pauses its streaming producer if too much data is
        buffered, and then resumes it.
        """
        client, server = self.client, self.server

        class SaveActionProducer(object):
            implements(IPushProducer)
            def __init__(self):
                self.actions = []

            def pauseProducing(self):
                self.actions.append("pause")

            def resumeProducing(self):
                self.actions.append("resume")
                # Unregister the producer so the connection can close
                client.protocol.transport.unregisterProducer()
                # This is why the code below waits for the server connection
                # first - so we have it to close here.  We close the server side
                # because win32evenreactor cannot reliably observe us closing
                # the client side (#5285).
                server.protocol.transport.loseConnection()

            def stopProducing(self):
                self.actions.append("stop")

        producer = SaveActionProducer()

        def clientConnected(proto):
            # Register a streaming producer and verify that it gets paused after
            # it writes more than the local send buffer can hold.
            proto.transport.registerProducer(producer, True)
            self.assertEquals(producer.actions, [])
            self.setWriteBufferSize(proto.transport, 500)
            proto.transport.writeSequence(["x" * 50] * 20)
            self.assertEquals(producer.actions, ["pause"])

        self._producerTest(clientConnected)
        # After the send buffer gets a chance to empty out a bit, the producer
        # should be resumed.
        self.assertEquals(producer.actions, ["pause", "resume"])


    def test_nonStreamingProducer(self):
        """
        C{writeSequence} pauses its producer if too much data is buffered only
        if this is a streaming producer.
        """
        client, server = self.client, self.server
        test = self

        class SaveActionProducer(object):
            implements(IPullProducer)
            def __init__(self):
                self.actions = []

            def resumeProducing(self):
                self.actions.append("resume")
                if self.actions.count("resume") == 2:
                    client.protocol.transport.stopConsuming()
                else:
                    test.setWriteBufferSize(client.protocol.transport, 500)
                    client.protocol.transport.writeSequence(["x" * 50] * 20)

            def stopProducing(self):
                self.actions.append("stop")

        producer = SaveActionProducer()

        def clientConnected(proto):
            # Register a non-streaming producer and verify that it is resumed
            # immediately.
            proto.transport.registerProducer(producer, False)
            self.assertEquals(producer.actions, ["resume"])

        self._producerTest(clientConnected)
        # After the local send buffer empties out, the producer should be
        # resumed again.
        self.assertEquals(producer.actions, ["resume", "resume"])


globals().update(TCPClientTestsBuilder.makeTestCaseClasses())
globals().update(TCPPortTestsBuilder.makeTestCaseClasses())
globals().update(TCPConnectionTestsBuilder.makeTestCaseClasses())
globals().update(WriteSequenceTests.makeTestCaseClasses())
