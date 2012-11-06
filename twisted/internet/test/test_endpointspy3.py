# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Tests for L{twisted.internet._endpointspy3}.
"""

from socket import AF_INET6, SOCK_STREAM, IPPROTO_TCP

from zope.interface import implementer
from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.test.proto_helpers import (
    MemoryReactor, RaisingMemoryReactor, StringTransport)
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet import (_endpointspy3 as endpoints, error, defer,
                              interfaces, reactor)

from twisted.test import __file__ as testInitPath
pemPath = FilePath(testInitPath.encode("utf-8")).sibling(b"server.pem")

try:
    from twisted.test.test_sslverify import makeCertificate
    from twisted.internet.ssl import (CertificateOptions, Certificate,
                                      PrivateCertificate)
    testCertificate = Certificate.loadPEM(pemPath.getContent())
    testPrivateCertificate = PrivateCertificate.loadPEM(pemPath.getContent())

    skipSSL = False
except ImportError:
    skipSSL = "OpenSSL is required to construct SSL Endpoints"


class TestProtocol(Protocol):
    """
    Protocol whose only function is to callback deferreds on the
    factory when it is connected or disconnected.
    """

    def __init__(self):
        self.data = []
        self.connectionsLost = []
        self.connectionMadeCalls = 0


    def logPrefix(self):
        return "A Test Protocol"


    def connectionMade(self):
        self.connectionMadeCalls += 1


    def dataReceived(self, data):
        self.data.append(data)


    def connectionLost(self, reason):
        self.connectionsLost.append(reason)



@implementer(interfaces.IHalfCloseableProtocol)
class TestHalfCloseableProtocol(TestProtocol):
    """
    A Protocol that implements L{IHalfCloseableProtocol} and records whether its
    C{readConnectionLost} and {writeConnectionLost} methods are called.

    @ivar readLost: A C{bool} indicating whether C{readConnectionLost} has been
        called.

    @ivar writeLost: A C{bool} indicating whether C{writeConnectionLost} has
        been called.
    """

    def __init__(self):
        TestProtocol.__init__(self)
        self.readLost = False
        self.writeLost = False


    def readConnectionLost(self):
        self.readLost = True


    def writeConnectionLost(self):
        self.writeLost = True



@implementer(interfaces.IFileDescriptorReceiver)
class TestFileDescriptorReceiverProtocol(TestProtocol):
    """
    A Protocol that implements L{IFileDescriptorReceiver} and records how its
    C{fileDescriptorReceived} method is called.

    @ivar receivedDescriptors: A C{list} containing all of the file descriptors
        passed to C{fileDescriptorReceived} calls made on this instance.
    """

    def connectionMade(self):
        TestProtocol.connectionMade(self)
        self.receivedDescriptors = []


    def fileDescriptorReceived(self, descriptor):
        self.receivedDescriptors.append(descriptor)



class TestFactory(ClientFactory):
    """
    Simple factory to be used both when connecting and listening. It contains
    two deferreds which are called back when my protocol connects and
    disconnects.
    """

    protocol = TestProtocol



class WrappingFactoryTests(unittest.TestCase):
    """
    Test the behaviour of our ugly implementation detail C{_WrappingFactory}.
    """
    def test_doStart(self):
        """
        L{_WrappingFactory.doStart} passes through to the wrapped factory's
        C{doStart} method, allowing application-specific setup and logging.
        """
        factory = ClientFactory()
        wf = endpoints._WrappingFactory(factory)
        wf.doStart()
        self.assertEqual(1, factory.numPorts)


    def test_doStop(self):
        """
        L{_WrappingFactory.doStop} passes through to the wrapped factory's
        C{doStop} method, allowing application-specific cleanup and logging.
        """
        factory = ClientFactory()
        factory.numPorts = 3
        wf = endpoints._WrappingFactory(factory)
        wf.doStop()
        self.assertEqual(2, factory.numPorts)


    def test_failedBuildProtocol(self):
        """
        An exception raised in C{buildProtocol} of our wrappedFactory
        results in our C{onConnection} errback being fired.
        """

        class BogusFactory(ClientFactory):
            """
            A one off factory whose C{buildProtocol} raises an C{Exception}.
            """

            def buildProtocol(self, addr):
                raise ValueError("My protocol is poorly defined.")


        wf = endpoints._WrappingFactory(BogusFactory())

        wf.buildProtocol(None)

        d = self.assertFailure(wf._onConnection, ValueError)
        d.addCallback(lambda e: self.assertEqual(
                e.args,
                ("My protocol is poorly defined.",)))

        return d


    def test_logPrefixPassthrough(self):
        """
        If the wrapped protocol provides L{ILoggingContext}, whatever is
        returned from the wrapped C{logPrefix} method is returned from
        L{_WrappingProtocol.logPrefix}.
        """
        wf = endpoints._WrappingFactory(TestFactory())
        wp = wf.buildProtocol(None)
        self.assertEqual(wp.logPrefix(), "A Test Protocol")


    def test_logPrefixDefault(self):
        """
        If the wrapped protocol does not provide L{ILoggingContext}, the wrapped
        protocol's class name is returned from L{_WrappingProtocol.logPrefix}.
        """
        class NoProtocol(object):
            pass
        factory = TestFactory()
        factory.protocol = NoProtocol
        wf = endpoints._WrappingFactory(factory)
        wp = wf.buildProtocol(None)
        self.assertEqual(wp.logPrefix(), "NoProtocol")


    def test_wrappedProtocolDataReceived(self):
        """
        The wrapped C{Protocol}'s C{dataReceived} will get called when our
        C{_WrappingProtocol}'s C{dataReceived} gets called.
        """
        wf = endpoints._WrappingFactory(TestFactory())
        p = wf.buildProtocol(None)
        p.makeConnection(None)

        p.dataReceived(b'foo')
        self.assertEqual(p._wrappedProtocol.data, [b'foo'])

        p.dataReceived(b'bar')
        self.assertEqual(p._wrappedProtocol.data, [b'foo', b'bar'])


    def test_wrappedProtocolTransport(self):
        """
        Our transport is properly hooked up to the wrappedProtocol when a
        connection is made.
        """
        wf = endpoints._WrappingFactory(TestFactory())
        p = wf.buildProtocol(None)

        dummyTransport = object()

        p.makeConnection(dummyTransport)

        self.assertEqual(p.transport, dummyTransport)

        self.assertEqual(p._wrappedProtocol.transport, dummyTransport)


    def test_wrappedProtocolConnectionLost(self):
        """
        Our wrappedProtocol's connectionLost method is called when
        L{_WrappingProtocol.connectionLost} is called.
        """
        tf = TestFactory()
        wf = endpoints._WrappingFactory(tf)
        p = wf.buildProtocol(None)

        p.connectionLost("fail")

        self.assertEqual(p._wrappedProtocol.connectionsLost, ["fail"])


    def test_clientConnectionFailed(self):
        """
        Calls to L{_WrappingFactory.clientConnectionLost} should errback the
        L{_WrappingFactory._onConnection} L{Deferred}
        """
        wf = endpoints._WrappingFactory(TestFactory())
        expectedFailure = Failure(error.ConnectError(string="fail"))

        wf.clientConnectionFailed(
            None,
            expectedFailure)

        errors = []
        def gotError(f):
            errors.append(f)

        wf._onConnection.addErrback(gotError)

        self.assertEqual(errors, [expectedFailure])


    def test_wrappingProtocolFileDescriptorReceiver(self):
        """
        Our L{_WrappingProtocol} should be an L{IFileDescriptorReceiver} if the
        wrapped protocol is.
        """
        connectedDeferred = None
        applicationProtocol = TestFileDescriptorReceiverProtocol()
        wrapper = endpoints._WrappingProtocol(
            connectedDeferred, applicationProtocol)
        self.assertTrue(interfaces.IFileDescriptorReceiver.providedBy(wrapper))
        self.assertTrue(verifyObject(interfaces.IFileDescriptorReceiver, wrapper))


    def test_wrappingProtocolNotFileDescriptorReceiver(self):
        """
        Our L{_WrappingProtocol} does not provide L{IHalfCloseableProtocol} if
        the wrapped protocol doesn't.
        """
        tp = TestProtocol()
        p = endpoints._WrappingProtocol(None, tp)
        self.assertFalse(interfaces.IFileDescriptorReceiver.providedBy(p))


    def test_wrappedProtocolFileDescriptorReceived(self):
        """
        L{_WrappingProtocol.fileDescriptorReceived} calls the wrapped protocol's
        C{fileDescriptorReceived} method.
        """
        wrappedProtocol = TestFileDescriptorReceiverProtocol()
        wrapper = endpoints._WrappingProtocol(
            defer.Deferred(), wrappedProtocol)
        wrapper.makeConnection(StringTransport())
        wrapper.fileDescriptorReceived(42)
        self.assertEqual(wrappedProtocol.receivedDescriptors, [42])


    def test_wrappingProtocolHalfCloseable(self):
        """
        Our L{_WrappingProtocol} should be an L{IHalfCloseableProtocol} if the
        C{wrappedProtocol} is.
        """
        cd = object()
        hcp = TestHalfCloseableProtocol()
        p = endpoints._WrappingProtocol(cd, hcp)
        self.assertEqual(
            interfaces.IHalfCloseableProtocol.providedBy(p), True)


    def test_wrappingProtocolNotHalfCloseable(self):
        """
        Our L{_WrappingProtocol} should not provide L{IHalfCloseableProtocol}
        if the C{WrappedProtocol} doesn't.
        """
        tp = TestProtocol()
        p = endpoints._WrappingProtocol(None, tp)
        self.assertEqual(
            interfaces.IHalfCloseableProtocol.providedBy(p), False)


    def test_wrappedProtocolReadConnectionLost(self):
        """
        L{_WrappingProtocol.readConnectionLost} should proxy to the wrapped
        protocol's C{readConnectionLost}
        """
        hcp = TestHalfCloseableProtocol()
        p = endpoints._WrappingProtocol(None, hcp)
        p.readConnectionLost()
        self.assertEqual(hcp.readLost, True)


    def test_wrappedProtocolWriteConnectionLost(self):
        """
        L{_WrappingProtocol.writeConnectionLost} should proxy to the wrapped
        protocol's C{writeConnectionLost}
        """
        hcp = TestHalfCloseableProtocol()
        p = endpoints._WrappingProtocol(None, hcp)
        p.writeConnectionLost()
        self.assertEqual(hcp.writeLost, True)



class ClientEndpointTestCaseMixin(object):
    """
    Generic test methods to be mixed into all client endpoint test classes.
    """
    def test_interface(self):
        """
        The endpoint provides L{interfaces.IStreamClientEndpoint}
        """
        clientFactory = object()
        ep, ignoredArgs, address = self.createClientEndpoint(MemoryReactor(), clientFactory)
        self.assertTrue(verifyObject(interfaces.IStreamClientEndpoint, ep))


    def retrieveConnectedFactory(self, reactor):
        """
        Retrieve a single factory that has connected using the given reactor.
        (This behavior is valid for TCP and SSL but needs to be overridden for
        UNIX.)

        @param reactor: a L{MemoryReactor}
        """
        return self.expectedClients(reactor)[0][2]


    def test_endpointConnectSuccess(self):
        """
        A client endpoint can connect and returns a deferred who gets called
        back with a protocol instance.
        """
        proto = object()
        mreactor = MemoryReactor()

        clientFactory = object()

        ep, expectedArgs, ignoredDest = self.createClientEndpoint(
            mreactor, clientFactory)

        d = ep.connect(clientFactory)

        receivedProtos = []

        def checkProto(p):
            receivedProtos.append(p)

        d.addCallback(checkProto)

        factory = self.retrieveConnectedFactory(mreactor)
        factory._onConnection.callback(proto)
        self.assertEqual(receivedProtos, [proto])

        expectedClients = self.expectedClients(mreactor)

        self.assertEqual(len(expectedClients), 1)
        self.assertConnectArgs(expectedClients[0], expectedArgs)


    def test_endpointConnectFailure(self):
        """
        If an endpoint tries to connect to a non-listening port it gets
        a C{ConnectError} failure.
        """
        expectedError = error.ConnectError(string="Connection Failed")

        mreactor = RaisingMemoryReactor(connectException=expectedError)

        clientFactory = object()

        ep, ignoredArgs, ignoredDest = self.createClientEndpoint(
            mreactor, clientFactory)

        d = ep.connect(clientFactory)

        receivedExceptions = []

        def checkFailure(f):
            receivedExceptions.append(f.value)

        d.addErrback(checkFailure)

        self.assertEqual(receivedExceptions, [expectedError])


    def test_endpointConnectingCancelled(self):
        """
        Calling L{Deferred.cancel} on the L{Deferred} returned from
        L{IStreamClientEndpoint.connect} is errbacked with an expected
        L{ConnectingCancelledError} exception.
        """
        mreactor = MemoryReactor()

        clientFactory = object()

        ep, ignoredArgs, address = self.createClientEndpoint(
            mreactor, clientFactory)

        d = ep.connect(clientFactory)

        receivedFailures = []

        def checkFailure(f):
            receivedFailures.append(f)

        d.addErrback(checkFailure)

        d.cancel()
        # When canceled, the connector will immediately notify its factory that
        # the connection attempt has failed due to a UserError.
        attemptFactory = self.retrieveConnectedFactory(mreactor)
        attemptFactory.clientConnectionFailed(None, Failure(error.UserError()))
        # This should be a feature of MemoryReactor: <http://tm.tl/5630>.

        self.assertEqual(len(receivedFailures), 1)

        failure = receivedFailures[0]

        self.assertIsInstance(failure.value, error.ConnectingCancelledError)
        self.assertEqual(failure.value.address, address)


    def test_endpointConnectNonDefaultArgs(self):
        """
        The endpoint should pass it's connectArgs parameter to the reactor's
        listen methods.
        """
        factory = object()

        mreactor = MemoryReactor()

        ep, expectedArgs, ignoredHost = self.createClientEndpoint(
            mreactor, factory,
            **self.connectArgs())

        ep.connect(factory)

        expectedClients = self.expectedClients(mreactor)

        self.assertEqual(len(expectedClients), 1)
        self.assertConnectArgs(expectedClients[0], expectedArgs)



class ServerEndpointTestCaseMixin(object):
    """
    Generic test methods to be mixed into all client endpoint test classes.
    """
    def test_interface(self):
        """
        The endpoint provides L{interfaces.IStreamServerEndpoint}.
        """
        factory = object()
        ep, ignoredArgs, ignoredDest = self.createServerEndpoint(
                MemoryReactor(), factory)
        self.assertTrue(verifyObject(interfaces.IStreamServerEndpoint, ep))


    def test_endpointListenSuccess(self):
        """
        An endpoint can listen and returns a deferred that gets called back
        with a port instance.
        """
        mreactor = MemoryReactor()

        factory = object()

        ep, expectedArgs, expectedHost = self.createServerEndpoint(
            mreactor, factory)

        d = ep.listen(factory)

        receivedHosts = []

        def checkPortAndServer(port):
            receivedHosts.append(port.getHost())

        d.addCallback(checkPortAndServer)

        self.assertEqual(receivedHosts, [expectedHost])
        self.assertEqual(self.expectedServers(mreactor), [expectedArgs])


    def test_endpointListenFailure(self):
        """
        When an endpoint tries to listen on an already listening port, a
        C{CannotListenError} failure is errbacked.
        """
        factory = object()
        exception = error.CannotListenError('', 80, factory)
        mreactor = RaisingMemoryReactor(listenException=exception)

        ep, ignoredArgs, ignoredDest = self.createServerEndpoint(
            mreactor, factory)

        d = ep.listen(object())

        receivedExceptions = []

        def checkFailure(f):
            receivedExceptions.append(f.value)

        d.addErrback(checkFailure)

        self.assertEqual(receivedExceptions, [exception])


    def test_endpointListenNonDefaultArgs(self):
        """
        The endpoint should pass it's listenArgs parameter to the reactor's
        listen methods.
        """
        factory = object()

        mreactor = MemoryReactor()

        ep, expectedArgs, ignoredHost = self.createServerEndpoint(
            mreactor, factory,
            **self.listenArgs())

        ep.listen(factory)

        expectedServers = self.expectedServers(mreactor)

        self.assertEqual(expectedServers, [expectedArgs])



class EndpointTestCaseMixin(ServerEndpointTestCaseMixin,
                            ClientEndpointTestCaseMixin):
    """
    Generic test methods to be mixed into all endpoint test classes.
    """



class TCP4EndpointsTestCase(EndpointTestCaseMixin, unittest.TestCase):
    """
    Tests for TCP IPv4 Endpoints.
    """

    def expectedServers(self, reactor):
        """
        @return: List of calls to L{IReactorTCP.listenTCP}
        """
        return reactor.tcpServers


    def expectedClients(self, reactor):
        """
        @return: List of calls to L{IReactorTCP.connectTCP}
        """
        return reactor.tcpClients


    def assertConnectArgs(self, receivedArgs, expectedArgs):
        """
        Compare host, port, timeout, and bindAddress in C{receivedArgs}
        to C{expectedArgs}.  We ignore the factory because we don't
        only care what protocol comes out of the
        C{IStreamClientEndpoint.connect} call.

        @param receivedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{timeout}, C{bindAddress}) that was passed to
            L{IReactorTCP.connectTCP}.
        @param expectedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{timeout}, C{bindAddress}) that we expect to have been passed
            to L{IReactorTCP.connectTCP}.
        """
        (host, port, ignoredFactory, timeout, bindAddress) = receivedArgs
        (expectedHost, expectedPort, _ignoredFactory,
         expectedTimeout, expectedBindAddress) = expectedArgs

        self.assertEqual(host, expectedHost)
        self.assertEqual(port, expectedPort)
        self.assertEqual(timeout, expectedTimeout)
        self.assertEqual(bindAddress, expectedBindAddress)


    def connectArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to connect.
        """
        return {'timeout': 10, 'bindAddress': ('localhost', 49595)}


    def listenArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to listen
        """
        return {'backlog': 100, 'interface': '127.0.0.1'}


    def createServerEndpoint(self, reactor, factory, **listenArgs):
        """
        Create an L{TCP4ServerEndpoint} and return the values needed to verify
        its behaviour.

        @param reactor: A fake L{IReactorTCP} that L{TCP4ServerEndpoint} can
            call L{IReactorTCP.listenTCP} on.
        @param factory: The thing that we expect to be passed to our
            L{IStreamServerEndpoint.listen} implementation.
        @param listenArgs: Optional dictionary of arguments to
            L{IReactorTCP.listenTCP}.
        """
        address = IPv4Address("TCP", "0.0.0.0", 0)

        if listenArgs is None:
            listenArgs = {}

        return (endpoints.TCP4ServerEndpoint(reactor,
                                             address.port,
                                             **listenArgs),
                (address.port, factory,
                 listenArgs.get('backlog', 50),
                 listenArgs.get('interface', '')),
                address)


    def createClientEndpoint(self, reactor, clientFactory, **connectArgs):
        """
        Create an L{TCP4ClientEndpoint} and return the values needed to verify
        its behavior.

        @param reactor: A fake L{IReactorTCP} that L{TCP4ClientEndpoint} can
            call L{IReactorTCP.connectTCP} on.
        @param clientFactory: The thing that we expect to be passed to our
            L{IStreamClientEndpoint.connect} implementation.
        @param connectArgs: Optional dictionary of arguments to
            L{IReactorTCP.connectTCP}
        """
        address = IPv4Address("TCP", "localhost", 80)

        return (endpoints.TCP4ClientEndpoint(reactor,
                                             address.host,
                                             address.port,
                                             **connectArgs),
                (address.host, address.port, clientFactory,
                 connectArgs.get('timeout', 30),
                 connectArgs.get('bindAddress', None)),
                address)



class TCP6EndpointsTestCase(EndpointTestCaseMixin, unittest.TestCase):
    """
    Tests for TCP IPv6 Endpoints.
    """

    def expectedServers(self, reactor):
        """
        @return: List of calls to L{IReactorTCP.listenTCP}
        """
        return reactor.tcpServers


    def expectedClients(self, reactor):
        """
        @return: List of calls to L{IReactorTCP.connectTCP}
        """
        return reactor.tcpClients


    def assertConnectArgs(self, receivedArgs, expectedArgs):
        """
        Compare host, port, timeout, and bindAddress in C{receivedArgs}
        to C{expectedArgs}.  We ignore the factory because we don't
        only care what protocol comes out of the
        C{IStreamClientEndpoint.connect} call.

        @param receivedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{timeout}, C{bindAddress}) that was passed to
            L{IReactorTCP.connectTCP}.
        @param expectedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{timeout}, C{bindAddress}) that we expect to have been passed
            to L{IReactorTCP.connectTCP}.
        """
        (host, port, ignoredFactory, timeout, bindAddress) = receivedArgs
        (expectedHost, expectedPort, _ignoredFactory,
         expectedTimeout, expectedBindAddress) = expectedArgs

        self.assertEqual(host, expectedHost)
        self.assertEqual(port, expectedPort)
        self.assertEqual(timeout, expectedTimeout)
        self.assertEqual(bindAddress, expectedBindAddress)


    def connectArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to connect.
        """
        return {'timeout': 10, 'bindAddress': ('localhost', 49595)}


    def listenArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to listen
        """
        return {'backlog': 100, 'interface': '::1'}


    def createServerEndpoint(self, reactor, factory, **listenArgs):
        """
        Create a L{TCP6ServerEndpoint} and return the values needed to verify
        its behaviour.

        @param reactor: A fake L{IReactorTCP} that L{TCP6ServerEndpoint} can
            call L{IReactorTCP.listenTCP} on.
        @param factory: The thing that we expect to be passed to our
            L{IStreamServerEndpoint.listen} implementation.
        @param listenArgs: Optional dictionary of arguments to
            L{IReactorTCP.listenTCP}.
        """
        interface = listenArgs.get('interface', '::')
        address = IPv6Address("TCP", interface, 0)

        if listenArgs is None:
            listenArgs = {}

        return (endpoints.TCP6ServerEndpoint(reactor,
                                             address.port,
                                             **listenArgs),
                (address.port, factory,
                 listenArgs.get('backlog', 50),
                 interface),
                address)


    def createClientEndpoint(self, reactor, clientFactory, **connectArgs):
        """
        Create a L{TCP6ClientEndpoint} and return the values needed to verify
        its behavior.

        @param reactor: A fake L{IReactorTCP} that L{TCP6ClientEndpoint} can
            call L{IReactorTCP.connectTCP} on.
        @param clientFactory: The thing that we expect to be passed to our
            L{IStreamClientEndpoint.connect} implementation.
        @param connectArgs: Optional dictionary of arguments to
            L{IReactorTCP.connectTCP}
        """
        address = IPv6Address("TCP", "::1", 80)

        return (endpoints.TCP6ClientEndpoint(reactor,
                                             address.host,
                                             address.port,
                                             **connectArgs),
                (address.host, address.port, clientFactory,
                 connectArgs.get('timeout', 30),
                 connectArgs.get('bindAddress', None)),
                address)


class TCP6EndpointNameResolutionTestCase(ClientEndpointTestCaseMixin,
                                         unittest.TestCase):
    """
    Tests for a TCP IPv6 Client Endpoint pointed at a hostname instead
    of an IPv6 address literal.
    """


    def createClientEndpoint(self, reactor, clientFactory, **connectArgs):
        """
        Create a L{TCP6ClientEndpoint} and return the values needed to verify
        its behavior.

        @param reactor: A fake L{IReactorTCP} that L{TCP6ClientEndpoint} can
            call L{IReactorTCP.connectTCP} on.
        @param clientFactory: The thing that we expect to be passed to our
            L{IStreamClientEndpoint.connect} implementation.
        @param connectArgs: Optional dictionary of arguments to
            L{IReactorTCP.connectTCP}
        """
        address = IPv6Address("TCP", "::2", 80)
        self.ep = endpoints.TCP6ClientEndpoint(reactor,
                                             'ipv6.example.com',
                                             address.port,
                                             **connectArgs)

        def testNameResolution(host):
            self.assertEqual("ipv6.example.com", host)
            data = [(AF_INET6, SOCK_STREAM, IPPROTO_TCP, '', ('::2', 0, 0, 0)),
                    (AF_INET6, SOCK_STREAM, IPPROTO_TCP, '', ('::3', 0, 0, 0)),
                    (AF_INET6, SOCK_STREAM, IPPROTO_TCP, '', ('::4', 0, 0, 0))]
            return defer.succeed(data)

        self.ep._nameResolution = testNameResolution

        return (self.ep,
                (address.host, address.port, clientFactory,
                 connectArgs.get('timeout', 30),
                 connectArgs.get('bindAddress', None)),
                address)


    def connectArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to connect.
        """
        return {'timeout': 10, 'bindAddress': ('localhost', 49595)}


    def expectedClients(self, reactor):
        """
        @return: List of calls to L{IReactorTCP.connectTCP}
        """
        return reactor.tcpClients


    def assertConnectArgs(self, receivedArgs, expectedArgs):
        """
        Compare host, port, timeout, and bindAddress in C{receivedArgs}
        to C{expectedArgs}.  We ignore the factory because we don't
        only care what protocol comes out of the
        C{IStreamClientEndpoint.connect} call.

        @param receivedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{timeout}, C{bindAddress}) that was passed to
            L{IReactorTCP.connectTCP}.
        @param expectedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{timeout}, C{bindAddress}) that we expect to have been passed
            to L{IReactorTCP.connectTCP}.
        """
        (host, port, ignoredFactory, timeout, bindAddress) = receivedArgs
        (expectedHost, expectedPort, _ignoredFactory,
         expectedTimeout, expectedBindAddress) = expectedArgs

        self.assertEqual(host, expectedHost)
        self.assertEqual(port, expectedPort)
        self.assertEqual(timeout, expectedTimeout)
        self.assertEqual(bindAddress, expectedBindAddress)


    def test_nameResolution(self):
        """
        While resolving host names, _nameResolution calls
        _deferToThread with _getaddrinfo.
        """
        calls = []

        def fakeDeferToThread(f, *args, **kwargs):
            calls.append((f, args, kwargs))
            return defer.Deferred()

        endpoint = endpoints.TCP6ClientEndpoint(reactor, 'ipv6.example.com',
            1234)
        fakegetaddrinfo = object()
        endpoint._getaddrinfo = fakegetaddrinfo
        endpoint._deferToThread = fakeDeferToThread
        endpoint.connect(TestFactory())
        self.assertEqual(
            [(fakegetaddrinfo, ("ipv6.example.com", 0, AF_INET6), {})], calls)



class SSL4EndpointsTestCase(EndpointTestCaseMixin,
                            unittest.TestCase):
    """
    Tests for SSL Endpoints.
    """
    if skipSSL:
        skip = skipSSL

    def expectedServers(self, reactor):
        """
        @return: List of calls to L{IReactorSSL.listenSSL}
        """
        return reactor.sslServers


    def expectedClients(self, reactor):
        """
        @return: List of calls to L{IReactorSSL.connectSSL}
        """
        return reactor.sslClients


    def assertConnectArgs(self, receivedArgs, expectedArgs):
        """
        Compare host, port, contextFactory, timeout, and bindAddress in
        C{receivedArgs} to C{expectedArgs}.  We ignore the factory because we
        don't only care what protocol comes out of the
        C{IStreamClientEndpoint.connect} call.

        @param receivedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{contextFactory}, C{timeout}, C{bindAddress}) that was passed to
            L{IReactorSSL.connectSSL}.
        @param expectedArgs: C{tuple} of (C{host}, C{port}, C{factory},
            C{contextFactory}, C{timeout}, C{bindAddress}) that we expect to
            have been passed to L{IReactorSSL.connectSSL}.
        """
        (host, port, ignoredFactory, contextFactory, timeout,
         bindAddress) = receivedArgs

        (expectedHost, expectedPort, _ignoredFactory, expectedContextFactory,
         expectedTimeout, expectedBindAddress) = expectedArgs

        self.assertEqual(host, expectedHost)
        self.assertEqual(port, expectedPort)
        self.assertEqual(contextFactory, expectedContextFactory)
        self.assertEqual(timeout, expectedTimeout)
        self.assertEqual(bindAddress, expectedBindAddress)


    def connectArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to connect.
        """
        return {'timeout': 10, 'bindAddress': ('localhost', 49595)}


    def listenArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to listen
        """
        return {'backlog': 100, 'interface': '127.0.0.1'}


    def setUp(self):
        """
        Set up client and server SSL contexts for use later.
        """
        self.sKey, self.sCert = makeCertificate(
            O="Server Test Certificate",
            CN="server")
        self.cKey, self.cCert = makeCertificate(
            O="Client Test Certificate",
            CN="client")
        self.serverSSLContext = CertificateOptions(
            privateKey=self.sKey,
            certificate=self.sCert,
            requireCertificate=False)
        self.clientSSLContext = CertificateOptions(
            requireCertificate=False)


    def createServerEndpoint(self, reactor, factory, **listenArgs):
        """
        Create an L{SSL4ServerEndpoint} and return the tools to verify its
        behaviour.

        @param factory: The thing that we expect to be passed to our
            L{IStreamServerEndpoint.listen} implementation.
        @param reactor: A fake L{IReactorSSL} that L{SSL4ServerEndpoint} can
            call L{IReactorSSL.listenSSL} on.
        @param listenArgs: Optional dictionary of arguments to
            L{IReactorSSL.listenSSL}.
        """
        address = IPv4Address("TCP", "0.0.0.0", 0)

        return (endpoints.SSL4ServerEndpoint(reactor,
                                             address.port,
                                             self.serverSSLContext,
                                             **listenArgs),
                (address.port, factory, self.serverSSLContext,
                 listenArgs.get('backlog', 50),
                 listenArgs.get('interface', '')),
                address)


    def createClientEndpoint(self, reactor, clientFactory, **connectArgs):
        """
        Create an L{SSL4ClientEndpoint} and return the values needed to verify
        its behaviour.

        @param reactor: A fake L{IReactorSSL} that L{SSL4ClientEndpoint} can
            call L{IReactorSSL.connectSSL} on.
        @param clientFactory: The thing that we expect to be passed to our
            L{IStreamClientEndpoint.connect} implementation.
        @param connectArgs: Optional dictionary of arguments to
            L{IReactorSSL.connectSSL}
        """
        address = IPv4Address("TCP", "localhost", 80)

        if connectArgs is None:
            connectArgs = {}

        return (endpoints.SSL4ClientEndpoint(reactor,
                                             address.host,
                                             address.port,
                                             self.clientSSLContext,
                                             **connectArgs),
                (address.host, address.port, clientFactory,
                 self.clientSSLContext,
                 connectArgs.get('timeout', 30),
                 connectArgs.get('bindAddress', None)),
                address)
