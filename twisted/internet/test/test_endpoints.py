# Copyright (c) 2007-2010 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test the C{I...Endpoint} implementations that wrap the L{IReactorTCP},
L{IReactorSSL}, and L{IReactorUNIX} interfaces found in
L{twisted.internet.endpoints}.
"""

from zope.interface import implements

from twisted.trial import unittest
from twisted.internet import error, interfaces
from twisted.internet import endpoints
from twisted.internet.address import IPv4Address, UNIXAddress
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.test.proto_helpers import MemoryReactor, RaisingMemoryReactor
from twisted.python.failure import Failure

try:
    from twisted.test.test_sslverify import makeCertificate
    from twisted.internet.ssl import CertificateOptions
    skipSSL = False
except ImportError:
    skipSSL = "SSL not available."


class TestProtocol(Protocol):
    """
    Protocol whose only function is to callback deferreds on the
    factory when it is connected or disconnected.
    """

    def __init__(self):
        self.data = []
        self.connectionsLost = []
        self.connectionMadeCalls = 0

    def connectionMade(self):
        self.connectionMadeCalls += 1


    def dataReceived(self, data):
        self.data.append(data)


    def connectionLost(self, reason):
        self.connectionsLost.append(reason)



class TestHalfCloseableProtocol(TestProtocol):
    """
    A Protocol that implements L{IHalfCloseableProtocol} and records that
    its C{readConnectionLost} and {writeConnectionLost} methods.
    """
    implements(interfaces.IHalfCloseableProtocol)

    def __init__(self):
        TestProtocol.__init__(self)
        self.readLost = False
        self.writeLost = False


    def readConnectionLost(self):
        self.readLost = True


    def writeConnectionLost(self):
        self.writeLost = True



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


        wf = endpoints._WrappingFactory(BogusFactory(), None)

        wf.buildProtocol(None)

        d = self.assertFailure(wf._onConnection, ValueError)
        d.addCallback(lambda e: self.assertEquals(
                e.args,
                ("My protocol is poorly defined.",)))

        return d


    def test_wrappedProtocolDataReceived(self):
        """
        The wrapped C{Protocol}'s C{dataReceived} will get called when our
        C{_WrappingProtocol}'s C{dataReceived} gets called.
        """
        wf = endpoints._WrappingFactory(TestFactory(), None)
        p = wf.buildProtocol(None)
        p.makeConnection(None)

        p.dataReceived('foo')
        self.assertEquals(p._wrappedProtocol.data, ['foo'])

        p.dataReceived('bar')
        self.assertEquals(p._wrappedProtocol.data, ['foo', 'bar'])


    def test_wrappedProtocolTransport(self):
        """
        Our transport is properly hooked up to the wrappedProtocol when a
        connection is made.
        """
        wf = endpoints._WrappingFactory(TestFactory(), None)
        p = wf.buildProtocol(None)

        dummyTransport = object()

        p.makeConnection(dummyTransport)

        self.assertEquals(p.transport, dummyTransport)

        self.assertEquals(p._wrappedProtocol.transport, dummyTransport)


    def test_wrappedProtocolConnectionLost(self):
        """
        Our wrappedProtocol's connectionLost method is called when
        L{_WrappingProtocol.connectionLost} is called.
        """
        tf = TestFactory()
        wf = endpoints._WrappingFactory(tf, None)
        p = wf.buildProtocol(None)

        p.connectionLost("fail")

        self.assertEquals(p._wrappedProtocol.connectionsLost, ["fail"])


    def test_clientConnectionFailed(self):
        """
        Calls to L{_WrappingFactory.clientConnectionLost} should errback the
        L{_WrappingFactory._onConnection} L{Deferred}
        """
        wf = endpoints._WrappingFactory(TestFactory(), None)
        expectedFailure = Failure(error.ConnectError(string="fail"))

        wf.clientConnectionFailed(
            None,
            expectedFailure)

        errors = []
        def gotError(f):
            errors.append(f)

        wf._onConnection.addErrback(gotError)

        self.assertEquals(errors, [expectedFailure])


    def test_wrappingProtocolHalfCloseable(self):
        """
        Our  L{_WrappingProtocol} should be an L{IHalfCloseableProtocol} if
        the C{wrappedProtocol} is.
        """
        cd = object()
        hcp = TestHalfCloseableProtocol()
        p = endpoints._WrappingProtocol(cd, hcp)
        self.assertEquals(
            interfaces.IHalfCloseableProtocol.providedBy(p), True)


    def test_wrappingProtocolNotHalfCloseable(self):
        """
        Our L{_WrappingProtocol} should not provide L{IHalfCloseableProtocol}
        if the C{WrappedProtocol} doesn't.
        """
        tp = TestProtocol()
        p = endpoints._WrappingProtocol(None, tp)
        self.assertEquals(
            interfaces.IHalfCloseableProtocol.providedBy(p), False)


    def test_wrappedProtocolReadConnectionLost(self):
        """
        L{_WrappingProtocol.readConnectionLost} should proxy to the wrapped
        protocol's C{readConnectionLost}
        """
        hcp = TestHalfCloseableProtocol()
        p = endpoints._WrappingProtocol(None, hcp)
        p.readConnectionLost()
        self.assertEquals(hcp.readLost, True)


    def test_wrappedProtocolWriteConnectionLost(self):
        """
        L{_WrappingProtocol.writeConnectionLost} should proxy to the wrapped
        protocol's C{writeConnectionLost}
        """
        hcp = TestHalfCloseableProtocol()
        p = endpoints._WrappingProtocol(None, hcp)
        p.writeConnectionLost()
        self.assertEquals(hcp.writeLost, True)



class EndpointTestCaseMixin(object):
    """
    Generic test methods to be mixed into all endpoint test classes.
    """

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
        self.assertEquals(receivedProtos, [proto])

        expectedClients = self.expectedClients(mreactor)

        self.assertEquals(len(expectedClients), 1)
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

        self.assertEquals(receivedExceptions, [expectedError])


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

        self.assertEquals(len(receivedFailures), 1)

        failure = receivedFailures[0]

        self.assertIsInstance(failure.value, error.ConnectingCancelledError)
        self.assertEquals(failure.value.address, address)


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

        self.assertEquals(receivedHosts, [expectedHost])
        self.assertEquals(self.expectedServers(mreactor), [expectedArgs])


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

        self.assertEquals(receivedExceptions, [exception])


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

        self.assertEquals(len(expectedClients), 1)
        self.assertConnectArgs(expectedClients[0], expectedArgs)


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

        self.assertEquals(expectedServers, [expectedArgs])



class TCP4EndpointsTestCase(EndpointTestCaseMixin,
                            unittest.TestCase):
    """
    Tests for TCP Endpoints.
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

        self.assertEquals(host, expectedHost)
        self.assertEquals(port, expectedPort)
        self.assertEquals(timeout, expectedTimeout)
        self.assertEquals(bindAddress, expectedBindAddress)


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

        self.assertEquals(host, expectedHost)
        self.assertEquals(port, expectedPort)
        self.assertEquals(contextFactory, expectedContextFactory)
        self.assertEquals(timeout, expectedTimeout)
        self.assertEquals(bindAddress, expectedBindAddress)


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



class UNIXEndpointsTestCase(EndpointTestCaseMixin,
                            unittest.TestCase):
    """
    Tests for UnixSocket Endpoints.
    """

    def retrieveConnectedFactory(self, reactor):
        """
        Override L{EndpointTestCaseMixin.retrieveConnectedFactory} to account
        for different index of 'factory' in C{connectUNIX} args.
        """
        return self.expectedClients(reactor)[0][1]

    def expectedServers(self, reactor):
        """
        @return: List of calls to L{IReactorUNIX.listenUNIX}
        """
        return reactor.unixServers


    def expectedClients(self, reactor):
        """
        @return: List of calls to L{IReactorUNIX.connectUNIX}
        """
        return reactor.unixClients


    def assertConnectArgs(self, receivedArgs, expectedArgs):
        """
        Compare path, timeout, checkPID in C{receivedArgs} to C{expectedArgs}.
        We ignore the factory because we don't only care what protocol comes
        out of the C{IStreamClientEndpoint.connect} call.

        @param receivedArgs: C{tuple} of (C{path}, C{timeout}, C{checkPID})
            that was passed to L{IReactorUNIX.connectUNIX}.
        @param expectedArgs: C{tuple} of (C{path}, C{timeout}, C{checkPID})
            that we expect to have been passed to L{IReactorUNIX.connectUNIX}.
        """

        (path, ignoredFactory, timeout, checkPID) = receivedArgs

        (expectedPath, _ignoredFactory, expectedTimeout,
         expectedCheckPID) = expectedArgs

        self.assertEquals(path, expectedPath)
        self.assertEquals(timeout, expectedTimeout)
        self.assertEquals(checkPID, expectedCheckPID)


    def connectArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to connect.
        """
        return {'timeout': 10, 'checkPID': 1}


    def listenArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to listen
        """
        return {'backlog': 100, 'mode': 0600, 'wantPID': 1}


    def createServerEndpoint(self, reactor, factory, **listenArgs):
        """
        Create an L{UNIXServerEndpoint} and return the tools to verify its
        behaviour.

        @param reactor: A fake L{IReactorUNIX} that L{UNIXServerEndpoint} can
            call L{IReactorUNIX.listenUNIX} on.
        @param factory: The thing that we expect to be passed to our
            L{IStreamServerEndpoint.listen} implementation.
        @param listenArgs: Optional dictionary of arguments to
            L{IReactorUNIX.listenUNIX}.
        """
        address = UNIXAddress(self.mktemp())

        return (endpoints.UNIXServerEndpoint(reactor, address.name,
                                             **listenArgs),
                (address.name, factory,
                 listenArgs.get('backlog', 50),
                 listenArgs.get('mode', 0666),
                 listenArgs.get('wantPID', 0)),
                address)


    def createClientEndpoint(self, reactor, clientFactory, **connectArgs):
        """
        Create an L{UNIXClientEndpoint} and return the values needed to verify
        its behaviour.

        @param reactor: A fake L{IReactorUNIX} that L{UNIXClientEndpoint} can
            call L{IReactorUNIX.connectUNIX} on.
        @param clientFactory: The thing that we expect to be passed to our
            L{IStreamClientEndpoint.connect} implementation.
        @param connectArgs: Optional dictionary of arguments to
            L{IReactorUNIX.connectUNIX}
        """
        address = UNIXAddress(self.mktemp())

        return (endpoints.UNIXClientEndpoint(reactor, address.name,
                                             **connectArgs),
                (address.name, clientFactory,
                 connectArgs.get('timeout', 30),
                 connectArgs.get('checkPID', 0)),
                address)



