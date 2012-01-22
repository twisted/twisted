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
from twisted.internet.error import DNSLookupError, ConnectionLost
from twisted.internet.error import ConnectionDone, ConnectionAborted
from twisted.internet.interfaces import (
    ILoggingContext, IResolverSimple, IConnector, IReactorFDSet,
    ITLSTransport)
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import (
    Deferred, DeferredList, succeed, fail, maybeDeferred, gatherResults)
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint
from twisted.internet.protocol import ServerFactory, ClientFactory, Protocol
from twisted.internet.interfaces import (
    IPushProducer, IPullProducer, IHalfCloseableProtocol)
from twisted.internet.protocol import ClientCreator
from twisted.internet.tcp import Connection, Server

from twisted.internet.test.connectionmixins import (
    LogObserverMixin, ConnectionTestsMixin, serverFactoryFor)
from twisted.internet.test.test_core import ObjectModelIntegrationMixin
from twisted.test.test_tcp import MyClientFactory, MyServerFactory
from twisted.test.test_tcp import ClosingProtocol

try:
    from twisted.internet.ssl import ClientContextFactory
except ImportError:
    ClientContextFactory = None

try:
    socket.socket(socket.AF_INET6, socket.SOCK_STREAM).close()
except socket.error, e:
    ipv6Skip = str(e)
else:
    ipv6Skip = None



if platform.isWindows():
    from twisted.internet.test import _win32ifaces
    getLinkLocalIPv6Addresses = _win32ifaces.win32GetLinkLocalIPv6Addresses
else:
    try:
        from twisted.internet.test import _posixifaces
    except ImportError:
        getLinkLocalIPv6Addresses = lambda: []
    else:
        getLinkLocalIPv6Addresses = _posixifaces.posixGetLinkLocalIPv6Addresses


def getLinkLocalIPv6Address():
    """
    Find and return a configured link local IPv6 address including a scope
    identifier using the % separation syntax.  If the system has no link local
    IPv6 addresses, raise L{SkipTest} instead.

    @raise SkipTest: if no link local address can be found or if the
        C{netifaces} module is not available.

    @return: a C{str} giving the address
    """
    addresses = getLinkLocalIPv6Addresses()
    if addresses:
        return addresses[0]
    raise SkipTest("Link local IPv6 address unavailable")



def findFreePort(interface='127.0.0.1', family=socket.AF_INET,
                 type=socket.SOCK_STREAM):
    """
    Ask the platform to allocate a free port on the specified interface,
    then release the socket and return the address which was allocated.

    @param interface: The local address to try to bind the port on.
    @type interface: C{str}

    @param type: The socket type which will use the resulting port.

    @return: A two-tuple of address and port, like that returned by
        L{socket.getsockname}.
    """
    probe = socket.socket(family, type)
    try:
        probe.bind((interface, 0))
        return probe.getsockname()
    finally:
        probe.close()



def connect(client, (host, port)):
    if '%' in host:
        address = socket.getaddrinfo(host, port)[0][4]
    else:
        address = (host, port)
    client.connect(address)



class BrokenContextFactory(object):
    """
    A context factory with a broken C{getContext} method, for exercising the
    error handling for such a case.
    """
    message = "Some path was wrong maybe"

    def getContext(self):
        raise ValueError(self.message)



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


    def setsockopt(self, *args):
        """
        Setsockopt is not implemented.  The method is provided since
        real sockets have it and some code expects it.  No behavior of
        L{FakeSocket} is affected by a call to it.
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

        # For some reason, pyobject/pygtk will not deliver the close
        # notification that should happen after the unregisterProducer call in
        # this test.  The selectable is in the write notification set, but no
        # notification ever arrives.  Probably for the same reason #5233 led
        # win32eventreactor to be broken.
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


    def test_badContext(self):
        """
        If the context factory passed to L{ITCPTransport.startTLS} raises an
        exception from its C{getContext} method, that exception is raised by
        L{ITCPTransport.startTLS}.
        """
        reactor = self.buildReactor()

        brokenFactory = BrokenContextFactory()
        exception = [None]

        serverFactory = ServerFactory()
        serverFactory.protocol = Protocol

        port = reactor.listenTCP(0, serverFactory)
        endpoint = self.clientEndpoint(reactor, port.getHost())

        clientFactory = ClientFactory()
        clientFactory.protocol = Protocol
        connectDeferred = endpoint.connect(clientFactory)

        def connected(protocol):
            if not ITLSTransport.providedBy(protocol.transport):
                exception[0] = "skip"
            else:
                exception[0] = self.assertRaises(
                    ValueError, protocol.transport.startTLS, brokenFactory)

        connectDeferred.addCallback(connected)
        connectDeferred.addErrback(log.err, "Unexpected startTLS behavior")
        connectDeferred.addCallback(lambda ign: reactor.stop())

        self.runReactor(reactor)

        if exception[0] == "skip":
            raise SkipTest("Reactor does not support ITLSTransport")
        self.assertEqual(BrokenContextFactory.message, str(exception[0]))



class StreamTransportTestsMixin(LogObserverMixin):
    """
    Mixin defining tests which apply to any port/connection based transport.
    """
    def test_startedListeningLogMessage(self):
        """
        When a port starts, a message including a description of the associated
        factory is logged.
        """
        loggedMessages = self.observe()
        reactor = self.buildReactor()
        class SomeFactory(ServerFactory):
            implements(ILoggingContext)
            def logPrefix(self):
                return "Crazy Factory"
        factory = SomeFactory()
        p = self.getListeningPort(reactor, factory)
        expectedMessage = self.getExpectedStartListeningLogMessage(
            p, "Crazy Factory")
        self.assertEqual((expectedMessage,), loggedMessages[0]['message'])


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
        p = self.getListeningPort(reactor, ServerFactory())
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
        port = self.getListeningPort(reactor, ServerFactory())
        self.assertFullyNewStyle(port)



class TCPPortTestsBuilder(ReactorBuilder, ObjectModelIntegrationMixin,
                          StreamTransportTestsMixin):
    """
    Tests for L{IReactorTCP.listenTCP}
    """
    def getListeningPort(self, reactor, factory):
        """
        Get a TCP port from a reactor.
        """
        return reactor.listenTCP(0, factory)


    def getExpectedStartListeningLogMessage(self, port, factory):
        """
        Get the message expected to be logged when a TCP port starts listening.
        """
        return "%s starting on %d" % (factory, port.getHost().port)


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


    def test_portGetHostOnIPv6(self):
        """
        When listening on an IPv6 address, L{IListeningPort.getHost} returns
        an L{IPv6Address} with C{host} and C{port} attributes reflecting the
        address the port is bound to.
        """
        reactor = self.buildReactor()
        host, portNumber = findFreePort(
            family=socket.AF_INET6, interface='::1')[:2]
        port = reactor.listenTCP(portNumber, ServerFactory(), interface=host)
        address = port.getHost()
        self.assertIsInstance(address, IPv6Address)
        self.assertEqual('::1', address.host)
        self.assertEqual(portNumber, address.port)
    if ipv6Skip:
        test_portGetHostOnIPv6.skip = ipv6Skip


    def test_portGetHostOnIPv6ScopeID(self):
        """
        When a link-local IPv6 address including a scope identifier is passed as
        the C{interface} argument to L{IReactorTCP.listenTCP}, the resulting
        L{IListeningPort} reports its address as an L{IPv6Address} with a host
        value that includes the scope identifier.
        """
        linkLocal = getLinkLocalIPv6Address()
        reactor = self.buildReactor()
        port = reactor.listenTCP(0, ServerFactory(), interface=linkLocal)
        address = port.getHost()
        self.assertIsInstance(address, IPv6Address)
        self.assertEqual(linkLocal, address.host)
    if ipv6Skip:
        test_portGetHostOnIPv6ScopeID.skip = ipv6Skip


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
            connect(client, (port.getHost().host, port.getHost().port))
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


    def test_buildProtocolIPv6Address(self):
        """
        When a connection is accepted to an IPv6 address, an L{IPv6Address} is
        passed to the factory's C{buildProtocol} method giving the peer's
        address.
        """
        interface = '::1'
        client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        observedAddress = self._buildProtocolAddressTest(client, interface)
        self.assertEqual(
            IPv6Address('TCP', *client.getsockname()[:2]), observedAddress)
    if ipv6Skip:
        test_buildProtocolIPv6Address.skip = ipv6Skip


    def test_buildProtocolIPv6AddressScopeID(self):
        """
        When a connection is accepted to a link-local IPv6 address, an
        L{IPv6Address} is passed to the factory's C{buildProtocol} method giving
        the peer's address, including a scope identifier.
        """
        interface = getLinkLocalIPv6Address()
        client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        observedAddress = self._buildProtocolAddressTest(client, interface)
        self.assertEqual(
            IPv6Address('TCP', *client.getsockname()[:2]), observedAddress)
    if ipv6Skip:
        test_buildProtocolIPv6AddressScopeID.skip = ipv6Skip


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
            connect(client, (port.getHost().host, port.getHost().port))
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


    def test_serverGetHostOnIPv6(self):
        """
        When a connection is accepted over IPv6, the server
        L{ITransport.getHost} method returns an L{IPv6Address} giving the
        address on which the server accepted the connection.
        """
        interface = '::1'
        client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        hostAddress = self._serverGetConnectionAddressTest(
            client, interface, 'getHost')
        self.assertEqual(
            IPv6Address('TCP', *client.getpeername()[:2]), hostAddress)
    if ipv6Skip:
        test_serverGetHostOnIPv6.skip = ipv6Skip


    def test_serverGetHostOnIPv6ScopeID(self):
        """
        When a connection is accepted over IPv6, the server
        L{ITransport.getHost} method returns an L{IPv6Address} giving the
        address on which the server accepted the connection, including the scope
        identifier.
        """
        interface = getLinkLocalIPv6Address()
        client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        hostAddress = self._serverGetConnectionAddressTest(
            client, interface, 'getHost')
        self.assertEqual(
            IPv6Address('TCP', *client.getpeername()[:2]), hostAddress)
    if ipv6Skip:
        test_serverGetHostOnIPv6ScopeID.skip = ipv6Skip


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


    def test_serverGetPeerOnIPv6(self):
        """
        When a connection is accepted over IPv6, the server
        L{ITransport.getPeer} method returns an L{IPv6Address} giving the
        address on the remote end of the connection.
        """
        interface = '::1'
        client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        peerAddress = self._serverGetConnectionAddressTest(
            client, interface, 'getPeer')
        self.assertEqual(
            IPv6Address('TCP', *client.getsockname()[:2]), peerAddress)
    if ipv6Skip:
        test_serverGetPeerOnIPv6.skip = ipv6Skip


    def test_serverGetPeerOnIPv6ScopeID(self):
        """
        When a connection is accepted over IPv6, the server
        L{ITransport.getPeer} method returns an L{IPv6Address} giving the
        address on the remote end of the connection, including the scope
        identifier.
        """
        interface = getLinkLocalIPv6Address()
        client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.addCleanup(client.close)
        peerAddress = self._serverGetConnectionAddressTest(
            client, interface, 'getPeer')
        self.assertEqual(
            IPv6Address('TCP', *client.getsockname()[:2]), peerAddress)
    if ipv6Skip:
        test_serverGetPeerOnIPv6ScopeID.skip = ipv6Skip



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


    def test_connectionLostAfterPausedTransport(self):
        """
        Alice connects to Bob.  Alice writes some bytes and then shuts down the
        connection.  Bob receives the bytes from the connection and then pauses
        the transport object.  Shortly afterwards Bob resumes the transport
        object.  At that point, Bob is notified that the connection has been
        closed.

        This is no problem for most reactors.  The underlying event notification
        API will probably just remind them that the connection has been closed.
        It is a little tricky for win32eventreactor (MsgWaitForMultipleObjects).
        MsgWaitForMultipleObjects will only deliver the close notification once.
        The reactor needs to remember that notification until Bob resumes the
        transport.
        """
        reactor = self.buildReactor()
        events = []
        class Pauser(Protocol):
            def dataReceived(self, bytes):
                events.append("paused")
                self.transport.pauseProducing()
                reactor.callLater(0, self.resume)

            def resume(self):
                events.append("resumed")
                self.transport.resumeProducing()

            def connectionLost(self, reason):
                # This is the event you have been waiting for.
                events.append("lost")
                reactor.stop()

        serverFactory = ServerFactory()
        serverFactory.protocol = Pauser
        port = reactor.listenTCP(0, serverFactory)

        cc = TCP4ClientEndpoint(reactor, '127.0.0.1', port.getHost().port)
        cf = ClientFactory()
        cf.protocol = Protocol
        clientDeferred = cc.connect(cf)
        def connected(client):
            client.transport.write("some bytes for you")
            client.transport.loseConnection()
        clientDeferred.addCallback(connected)

        self.runReactor(reactor)
        self.assertEqual(events, ["paused", "resumed", "lost"])


    def test_doubleHalfClose(self):
        """
        If one side half-closes its connection, and then the other side of the
        connection calls C{loseWriteConnection}, and then C{loseConnection} in
        {writeConnectionLost}, the connection is closed correctly.

        This rather obscure case used to fail (see ticket #3037).
        """
        reactor = self.buildReactor()

        class ListenerProtocol(Protocol):
            implements(IHalfCloseableProtocol)

            def readConnectionLost(self):
                self.transport.loseWriteConnection()

            def writeConnectionLost(self):
                self.transport.loseConnection()

            def connectionLost(self, reason):
                reactor.stop()

        factory = ServerFactory()
        factory.protocol = ListenerProtocol
        port = reactor.listenTCP(0, factory, interface="127.0.0.1")
        self.addCleanup(port.stopListening)

        cc = TCP4ClientEndpoint(reactor, '127.0.0.1', port.getHost().port)
        cf = ClientFactory()
        cf.protocol = Protocol
        clientDeferred = cc.connect(cf)
        def connected(client):
            client.transport.loseWriteConnection()
        clientDeferred.addCallback(connected)

        # If test fails, reactor won't stop and we'll hit timeout:
        self.runReactor(reactor, timeout=1)



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


    def test_writeSequenceWithUnicodeRaisesException(self):
        """
        C{writeSequence} with an element in the sequence of type unicode raises
        C{TypeError}.
        """
        client, server = self.client, self.server
        reactor = self.buildReactor()

        port = reactor.listenTCP(0, server)
        self.addCleanup(port.stopListening)

        connector = reactor.connectTCP(
            "127.0.0.1", port.getHost().port, client)
        self.addCleanup(connector.disconnect)

        def serverConnected(proto):
            log.msg("server connected %s" % proto)
            exc = self.assertRaises(
                TypeError,
                proto.transport.writeSequence, [u"Unicode is not kosher"])
            self.assertEquals(str(exc), "Data must not be unicode")

        d = server.protocolConnectionMade.addCallback(serverConnected)
        d.addErrback(log.err)
        d.addCallback(lambda ignored: reactor.stop())

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



class AbortServerProtocol(Protocol):
    """
    Generic server protocol for abortConnection() tests.
    """

    def connectionLost(self, reason):
        self.factory.done.callback(reason)
        del self.factory.done



class ServerAbortsTwice(AbortServerProtocol):
    """
    Call abortConnection() twice.
    """

    def dataReceived(self, data):
        self.transport.abortConnection()
        self.transport.abortConnection()



class ServerAbortsThenLoses(AbortServerProtocol):
    """
    Call abortConnection() followed by loseConnection().
    """

    def dataReceived(self, data):
        self.transport.abortConnection()
        self.transport.loseConnection()



class AbortServerWritingProtocol(AbortServerProtocol):
    """
    Protocol that writes data upon connection.
    """

    def connectionMade(self):
        """
        Tell the client that the connection is set up and it's time to abort.
        """
        self.transport.write("ready")



class ReadAbortServerProtocol(AbortServerWritingProtocol):
    """
    Server that should never receive any data, except 'X's which are written
    by the other side of the connection before abortConnection, and so might
    possibly arrive.
    """

    def dataReceived(self, data):
        if data.replace('X', ''):
            raise Exception("Unexpectedly received data.")



class NoReadServer(AbortServerProtocol):
    """
    Stop reading immediately on connection.

    This simulates a lost connection that will cause the other side to time
    out, and therefore call abortConnection().
    """

    def connectionMade(self):
        self.transport.stopReading()



class EventualNoReadServer(AbortServerProtocol):
    """
    Like NoReadServer, except we Wait until some bytes have been delivered
    before stopping reading. This means TLS handshake has finished, where
    applicable.
    """

    gotData = False
    stoppedReading = False


    def dataReceived(self, data):
        if not self.gotData:
            self.gotData = True
            self.transport.registerProducer(self, False)
            self.transport.write("hello")


    def resumeProducing(self):
        if self.stoppedReading:
            return
        self.stoppedReading = True
        # We've written out the data:
        self.transport.stopReading()


    def pauseProducing(self):
        pass


    def stopProducing(self):
        pass



class AbortServerFactory(ServerFactory):
    """
    Server factory for abortConnection() tests.
    """

    def __init__(self, done, serverClass, reactor):
        self.done = done
        self.serverClass = serverClass
        self.reactor = reactor

    def buildProtocol(self, addr):
        p = self.serverClass()
        p.factory = self
        self.proto = p
        return p


class BaseAbortingClient(Protocol):
    """
    Base class for abort-testing clients.
    """

    inReactorMethod = False

    def __init__(self, done, reactor):
        self.done = done
        self.reactor = reactor


    def connectionLost(self, reason):
        if self.inReactorMethod:
            raise RuntimeError("BUG: connectionLost was called re-entrantly!")
        self.done.callback(reason)
        del self.done



class WritingButNotAbortingClient(BaseAbortingClient):
    """
    Write data, but don't abort.
    """

    def connectionMade(self):
        self.transport.write("hello")



class AbortingClient(BaseAbortingClient):
    """
    Call abortConnection() after writing some data.
    """

    def dataReceived(self, data):
        """
        Some data was received, so the connection is set up.
        """
        self.inReactorMethod = True
        self.writeAndAbort()
        self.inReactorMethod = False


    def writeAndAbort(self):
        # X is written before abortConnection, and so there is a chance it
        # might arrive. Y is written after, and so no Ys should ever be
        # delivered:
        self.transport.write("X" * 10000)
        self.transport.abortConnection()
        self.transport.write("Y" * 10000)



class AbortingTwiceClient(AbortingClient):
    """
    Call abortConnection() twice, after writing some data.
    """

    def writeAndAbort(self):
        AbortingClient.writeAndAbort(self)
        self.transport.abortConnection()



class AbortingThenLosingClient(AbortingClient):
    """
    Call abortConnection() and then loseConnection().
    """

    def writeAndAbort(self):
        AbortingClient.writeAndAbort(self)
        self.transport.loseConnection()



class ProducerAbortingClient(Protocol):
    """
    Call abortConnection from doWrite, via resumeProducing.
    """

    inReactorMethod = True

    def __init__(self, done, reactor):
        self.done = done
        self.reactor = reactor
        self.producerStopped = False


    def write(self):
        self.transport.write("lalala" * 127000)
        self.inRegisterProducer = True
        self.transport.registerProducer(self, False)
        self.inRegisterProducer = False


    def connectionMade(self):
        self.write()


    def resumeProducing(self):
        self.inReactorMethod = True
        if not self.inRegisterProducer:
            self.transport.abortConnection()
        self.inReactorMethod = False


    def stopProducing(self):
        self.producerStopped = True


    def connectionLost(self, reason):
        if not self.producerStopped:
            raise RuntimeError("BUG: stopProducing() was never called.")
        if self.inReactorMethod:
            raise RuntimeError("BUG: connectionLost called re-entrantly!")
        self.done.callback(reason)
        del self.done



class StreamingProducerClient(Protocol):
    """
    Call abortConnection() when the other side has stopped reading.

    In particular, we want to call abortConnection() only once our local
    socket hits a state where it is no longer writeable. This helps emulate
    the most common use case for abortConnection(), closing a connection after
    a timeout, with write buffers being full.

    Since it's very difficult to know when this actually happens, we just
    write a lot of data, and assume at that point no more writes will happen.
    """

    def __init__(self, done, reactor):
        self.done = done
        self.paused = False
        self.reactor = reactor
        self.extraWrites = 0
        self.inReactorMethod = False


    def connectionMade(self):
        self.write()


    def write(self):
        """
        Write large amount to transport, then wait for a while for buffers to
        fill up.
        """
        self.transport.registerProducer(self, True)
        for i in range(100):
            self.transport.write("1234567890" * 32000)


    def resumeProducing(self):
        self.paused = False


    def stopProducing(self):
        pass


    def pauseProducing(self):
        """
        Called when local buffer fills up.

        The goal is to hit the point where the local file descriptor is not
        writeable (or the moral equivalent). The fact that pauseProducing has
        been called is not sufficient, since that can happen when Twisted's
        buffers fill up but OS hasn't gotten any writes yet. We want to be as
        close as possible to every buffer (including OS buffers) being full.

        So, we wait a bit more after this for Twisted to write out a few
        chunks, then abortConnection.
        """
        if self.paused:
            return
        self.paused = True
        # The amount we wait is arbitrary, we just want to make sure some
        # writes have happened and outgoing OS buffers filled up -- see
        # http://twistedmatrix.com/trac/ticket/5303 for details:
        self.reactor.callLater(0.01, self.doAbort)


    def doAbort(self):
        if not self.paused:
            log.err(RuntimeError("BUG: We should be paused a this point."))
        self.inReactorMethod = True
        self.transport.abortConnection()
        self.inReactorMethod = False


    def connectionLost(self, reason):
        # Tell server to start reading again so it knows to go away:
        self.serverFactory.proto.transport.startReading()
        self.done.callback(reason)
        del self.done



class StreamingProducerClientLater(StreamingProducerClient):
    """
    Call abortConnection() from dataReceived, after bytes have been
    exchanged.
    """

    def connectionMade(self):
        self.transport.write("hello")
        self.gotData = False


    def dataReceived(self, data):
        if not self.gotData:
            self.gotData = True
            self.write()


class ProducerAbortingClientLater(ProducerAbortingClient):
    """
    Call abortConnection from doWrite, via resumeProducing.

    Try to do so after some bytes have already been exchanged, so we
    don't interrupt SSL handshake.
    """

    def connectionMade(self):
        # Override base class connectionMade().
        pass


    def dataReceived(self, data):
        self.write()



class DataReceivedRaisingClient(AbortingClient):
    """
    Call abortConnection(), and then throw exception, from dataReceived.
    """

    def dataReceived(self, data):
        self.transport.abortConnection()
        raise ZeroDivisionError("ONO")



class ResumeThrowsClient(ProducerAbortingClient):
    """
    Call abortConnection() and throw exception from resumeProducing().
    """

    def resumeProducing(self):
        if not self.inRegisterProducer:
            self.transport.abortConnection()
            raise ZeroDivisionError("ono!")


    def connectionLost(self, reason):
        # Base class assertion about stopProducing being called isn't valid;
        # if the we blew up in resumeProducing, consumers are justified in
        # giving up on the producer and not calling stopProducing.
        self.done.callback(reason)
        del self.done



class AbortConnectionMixin(object):
    """
    Unit tests for L{ITransport.abortConnection}.
    """

    def runAbortTest(self, clientClass, serverClass,
                     clientConnectionLostReason=None):
        """
        A test runner utility function, which hooks up a matched pair of client
        and server protocols.

        We then run the reactor until both sides have disconnected, and then
        verify that the right exception resulted.
        """
        reactor = self.buildReactor()
        serverDoneDeferred = Deferred()
        clientDoneDeferred = Deferred()

        server = AbortServerFactory(serverDoneDeferred, serverClass, reactor)
        serverport = self.listen(reactor, server)

        c = ClientCreator(reactor, clientClass, clientDoneDeferred, reactor)
        d = self.connect(c, serverport)
        def addServer(client):
            client.serverFactory = server
        d.addCallback(addServer)

        serverReason = []
        clientReason = []
        serverDoneDeferred.addBoth(serverReason.append)
        clientDoneDeferred.addBoth(clientReason.append)
        d.addCallback(lambda x: clientDoneDeferred)
        d.addCallback(lambda x: serverDoneDeferred)

        d.addCallback(lambda x: serverport.stopListening())
        def verifyReactorIsClean(ignore):
            if clientConnectionLostReason is not None:
                self.flushLoggedErrors(clientConnectionLostReason)
            self.assertEqual(reactor.removeAll(), [])
            # The reactor always has a timeout added in buildReactor():
            delayedCalls = reactor.getDelayedCalls()
            self.assertEqual(len(delayedCalls), 1, map(str, delayedCalls))
        d.addCallback(verifyReactorIsClean)

        d.addCallback(lambda ignored: reactor.stop())
        # If we get error, make sure test still exits:
        def errorHandler(err):
            log.err(err)
            reactor.stop()
        d.addErrback(errorHandler)

        self.runReactor(reactor, timeout=10)

        clientExpectedExceptions = (ConnectionAborted, ConnectionLost)
        serverExpectedExceptions = (ConnectionLost, ConnectionDone)
        # In TLS tests we may get SSL.Error instead of ConnectionLost,
        # since we're trashing the TLS protocol layer.
        try:
            from OpenSSL import SSL
        except ImportError:
            SSL = None
        if SSL:
            clientExpectedExceptions = clientExpectedExceptions + (SSL.Error,)
            serverExpectedExceptions = serverExpectedExceptions + (SSL.Error,)

        if clientConnectionLostReason:
            self.assertIsInstance(clientReason[0].value,
                                  (clientConnectionLostReason,) + clientExpectedExceptions)
        else:
            self.assertIsInstance(clientReason[0].value, clientExpectedExceptions)
        self.assertIsInstance(serverReason[0].value, serverExpectedExceptions)


    def test_dataReceivedAbort(self):
        """
        abortConnection() is called in dataReceived. The protocol should be
        disconnected, but connectionLost should not be called re-entrantly.
        """
        return self.runAbortTest(AbortingClient, ReadAbortServerProtocol)


    def test_clientAbortsConnectionTwice(self):
        """
        abortConnection() is called twice by client.

        No exception should be thrown, and the connection will be closed.
        """
        return self.runAbortTest(AbortingTwiceClient, ReadAbortServerProtocol)


    def test_clientAbortsConnectionThenLosesConnection(self):
        """
        Client calls abortConnection(), followed by loseConnection().

        No exception should be thrown, and the connection will be closed.
        """
        return self.runAbortTest(AbortingThenLosingClient,
                                 ReadAbortServerProtocol)


    def test_serverAbortsConnectionTwice(self):
        """
        abortConnection() is called twice by server.

        No exception should be thrown, and the connection will be closed.
        """
        return self.runAbortTest(WritingButNotAbortingClient, ServerAbortsTwice,
                                 clientConnectionLostReason=ConnectionLost)


    def test_serverAbortsConnectionThenLosesConnection(self):
        """
        Server calls abortConnection(), followed by loseConnection().

        No exception should be thrown, and the connection will be closed.
        """
        return self.runAbortTest(WritingButNotAbortingClient,
                                 ServerAbortsThenLoses,
                                 clientConnectionLostReason=ConnectionLost)


    def test_resumeProducingAbort(self):
        """
        abortConnection() is called in resumeProducing, before any bytes have
        been exchanged. The protocol should be disconnected, but
        connectionLost should not be called re-entrantly.
        """
        self.runAbortTest(ProducerAbortingClient,
                          AbortServerProtocol)


    def test_resumeProducingAbortLater(self):
        """
        abortConnection() is called in resumeProducing, after some
        bytes have been exchanged. The protocol should be disconnected.
        """
        return self.runAbortTest(ProducerAbortingClientLater,
                                 AbortServerWritingProtocol)


    def test_fullWriteBuffer(self):
        """
        abortConnection() triggered by the write buffer being full.

        In particular, the server side stops reading. This is supposed
        to simulate a realistic timeout scenario where the client
        notices the server is no longer accepting data.

        The protocol should be disconnected, but connectionLost should not be
        called re-entrantly.
        """
        self.runAbortTest(StreamingProducerClient,
                          NoReadServer)


    def test_fullWriteBufferAfterByteExchange(self):
        """
        abortConnection() is triggered by a write buffer being full.

        However, this buffer is filled after some bytes have been exchanged,
        allowing a TLS handshake if we're testing TLS. The connection will
        then be lost.
        """
        return self.runAbortTest(StreamingProducerClientLater,
                                 EventualNoReadServer)


    def test_dataReceivedThrows(self):
        """
        dataReceived calls abortConnection(), and then raises an exception.

        The connection will be lost, with the thrown exception
        (C{ZeroDivisionError}) as the reason on the client. The idea here is
        that bugs should not be masked by abortConnection, in particular
        unexpected exceptions.
        """
        self.runAbortTest(DataReceivedRaisingClient,
                          AbortServerWritingProtocol,
                          clientConnectionLostReason=ZeroDivisionError)


    def test_resumeProducingThrows(self):
        """
        resumeProducing calls abortConnection(), and then raises an exception.

        The connection will be lost, with the thrown exception
        (C{ZeroDivisionError}) as the reason on the client. The idea here is
        that bugs should not be masked by abortConnection, in particular
        unexpected exceptions.
        """
        self.runAbortTest(ResumeThrowsClient,
                          AbortServerProtocol,
                          clientConnectionLostReason=ZeroDivisionError)




class AbortConnectionTestCase(ReactorBuilder, AbortConnectionMixin):
    """
    TCP-specific L{AbortConnectionMixin} tests.
    """

    def listen(self, reactor, server):
        """
        Listen with the given protocol factory.
        """
        return reactor.listenTCP(0, server, interface="127.0.0.1")


    def connect(self, clientcreator, serverport, *a, **k):
        """
        Connect a client to the listening server port.  Return the resulting
        Deferred.
        """
        return clientcreator.connectTCP(serverport.getHost().host,
                                        serverport.getHost().port)

globals().update(AbortConnectionTestCase.makeTestCaseClasses())
