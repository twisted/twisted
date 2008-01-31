# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test for L{twisted.web.proxy}.
"""

from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransportWithDisconnection
from twisted.internet.error import ConnectionDone

from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.proxy import ReverseProxyResource, ProxyClientFactory
from twisted.web.proxy import ProxyClient, ProxyRequest, ReverseProxyRequest



class FakeReactor(object):
    """
    A fake reactor to be used in tests.

    @ivar connect: a list that keeps track of connection attempts (ie, calls
        to C{connectTCP}).
    @type connect: C{list}
    """

    def __init__(self):
        """
        Initialize the C{connect} list.
        """
        self.connect = []


    def connectTCP(self, host, port, factory):
        """
        Fake L{reactor.connectTCP}, that does nothing but log the call.
        """
        self.connect.append([host, port, factory])



class ReverseProxyResourceTestCase(TestCase):
    """
    Tests for L{ReverseProxyResource}.
    """

    def _testRender(self, uri, expectedURI):
        """
        Check that a request pointing at C{uri} produce a new proxy connection,
        with the path of this request pointing at C{expectedURI}.
        """
        root = Resource()
        reactor = FakeReactor()
        resource = ReverseProxyResource("127.0.0.1", 1234, "/path", reactor)
        root.putChild('index', resource)
        site = Site(root)

        transport = StringTransportWithDisconnection()
        channel = site.buildProtocol(None)
        channel.makeConnection(transport)
        # Clear the timeout if the tests failed
        self.addCleanup(channel.connectionLost, None)

        channel.dataReceived("GET %s HTTP/1.1\r\nAccept: text/html\r\n\r\n" %
                             (uri,))

        # Check that one connection has been created, to the good host/port
        self.assertEquals(len(reactor.connect), 1)
        self.assertEquals(reactor.connect[0][0], "127.0.0.1")
        self.assertEquals(reactor.connect[0][1], 1234)

        # Check the factory passed to the connect, and its given path
        factory = reactor.connect[0][2]
        self.assertIsInstance(factory, ProxyClientFactory)
        self.assertEquals(factory.rest, expectedURI)
        self.assertEquals(factory.headers["host"], "127.0.0.1:1234")


    def test_render(self):
        """
        Test that L{ReverseProxyResource.render} initiates a connection to the
        given server with a L{ProxyClientFactory} as parameter.
        """
        return self._testRender("/index", "/path")


    def test_renderWithQuery(self):
        """
        Test that L{ReverseProxyResource.render} passes query parameters to the
        created factory.
        """
        return self._testRender("/index?foo=bar", "/path?foo=bar")


    def test_getChild(self):
        """
        The L{ReverseProxyResource.getChild} method should return a resource
        instance with the same class as the originating resource, forward port
        and host values, and update the path value with the value passed.
        """
        resource = ReverseProxyResource("127.0.0.1", 1234, "/path")
        child = resource.getChild('foo', None)
        # The child should keep the same class
        self.assertIsInstance(child, ReverseProxyResource)
        self.assertEquals(child.path, "/path/foo")
        self.assertEquals(child.port, 1234)
        self.assertEquals(child.host, "127.0.0.1")


    def test_getChildWithSpecial(self):
        """
        The L{ReverseProxyResource} return by C{getChild} has a path which has
        already been quoted.
        """
        resource = ReverseProxyResource("127.0.0.1", 1234, "/path")
        child = resource.getChild(' /%', None)
        self.assertEqual(child.path, "/path/%20%2F%25")



class DummyParent(object):
    """
    A dummy parent request that holds a channel and its transport.

    @ivar channel: the request channel.
    @ivar transport: the transport of the channel.
    """

    def __init__(self, channel):
        """
        Hold a reference to the channel and its transport.
        """
        self.channel = channel
        self.transport = channel.transport



class DummyChannel(object):
    """
    A dummy HTTP channel, that does nothing but holds a transport and saves
    connection lost.

    @ivar transport: the transport used by the client.
    @ivar lostReason: the reason saved at connection lost.
    """

    def __init__(self, transport):
        """
        Hold a reference to the transport.
        """
        self.transport = transport
        self.lostReason = None


    def connectionLost(self, reason):
        """
        Keep track of the connection lost reason.
        """
        self.lostReason = reason



class ProxyClientTestCase(TestCase):
    """
    Tests for L{ProxyClient}.
    """

    def _testDataForward(self, data, method="GET", body=""):
        """
        Build a fake proxy connection, and send C{data} over it, checking that
        it's forwarded to the originating request.
        """
        # Connect everything
        clientTransport = StringTransportWithDisconnection()
        serverTransport = StringTransportWithDisconnection()
        channel = DummyChannel(serverTransport)
        parent = DummyParent(channel)
        serverTransport.protocol = channel

        client = ProxyClient(method, '/foo', 'HTTP/1.0',
                             {"accept": "text/html"}, body, parent)
        clientTransport.protocol = client
        client.makeConnection(clientTransport)

        # Check data sent
        self.assertEquals(clientTransport.value(),
            "%s /foo HTTP/1.0\r\n"
            "connection: close\r\n"
            "accept: text/html\r\n\r\n%s" % (method, body))

        # Fake an answer
        client.dataReceived(data)

        # Check that the data has been forwarded
        self.assertEquals(serverTransport.value(), data)

        clientTransport.loseConnection()
        self.assertIsInstance(channel.lostReason, ConnectionDone)


    def test_forward(self):
        """
        When connected to the server, L{ProxyClient} should send the saved
        request, with modifications of the headers, and then forward the result
        to the parent request.
        """
        return self._testDataForward("200 OK\r\nFoo: bar\r\n\r\nSome data\r\n")


    def test_postData(self):
        """
        Try to post content in the request, and check that the proxy client
        forward the body of the request.
        """
        return self._testDataForward(
            "200 OK\r\nFoo: bar\r\n\r\nSome data\r\n", "POST", "Some content")


    def test_statusWithMessage(self):
        """
        If the response contains a status with a message, it should be
        forwarded to the parent request with all the information.
        """
        return self._testDataForward("404 Not Found\r\n")


    def test_headersCleanups(self):
        """
        The headers given at initialization should be modified:
        B{proxy-connection} should be removed if present, and B{connection}
        should be added.
        """
        client = ProxyClient('GET', '/foo', 'HTTP/1.0',
                {"accept": "text/html", "proxy-connection": "foo"}, '', None)
        self.assertEquals(client.headers,
                {"accept": "text/html", "connection": "close"})



class ProxyClientFactoryTestCase(TestCase):
    """
    Tests for L{ProxyClientFactory}.
    """

    def test_connectionFailed(self):
        """
        Check that L{ProxyClientFactory.clientConnectionFailed} produces
        a B{501} response to the parent request.
        """
        serverTransport = StringTransportWithDisconnection()
        channel = DummyChannel(serverTransport)
        parent = DummyParent(channel)
        serverTransport.protocol = channel
        factory = ProxyClientFactory('GET', '/foo', 'HTTP/1.0',
                                     {"accept": "text/html"}, '', parent)

        factory.clientConnectionFailed(None, None)
        self.assertEquals(serverTransport.value(),
                "HTTP/1.0 501 Gateway error\r\n"
                "Content-Type: text/html\r\n\r\n"
                "<H1>Could not connect</H1>")
        self.assertIsInstance(channel.lostReason, ConnectionDone)


    def test_buildProtocol(self):
        """
        L{ProxyClientFactory.buildProtocol} should produce a L{ProxyClient}
        with the same values of attributes (with updates on the headers).
        """
        factory = ProxyClientFactory('GET', '/foo', 'HTTP/1.0',
                                     {"accept": "text/html"}, 'Some data',
                                     None)
        proto = factory.buildProtocol(None)
        self.assertIsInstance(proto, ProxyClient)
        self.assertEquals(proto.command, 'GET')
        self.assertEquals(proto.rest, '/foo')
        self.assertEquals(proto.data, 'Some data')
        self.assertEquals(proto.headers,
                          {"accept": "text/html", "connection": "close"})



class ProxyRequestTestCase(TestCase):
    """
    Tests for L{ProxyRequest}.
    """

    def _testProcess(self, uri, expectedURI, method="GET", data=""):
        """
        Build a request pointing at C{uri}, and check that a proxied request
        is created, pointing a C{expectedURI}.
        """
        transport = StringTransportWithDisconnection()
        channel = DummyChannel(transport)
        reactor = FakeReactor()
        request = ProxyRequest(channel, False, reactor)
        request.gotLength(len(data))
        request.handleContentChunk(data)
        request.requestReceived(method, 'http://example.com%s' % (uri,),
                                'HTTP/1.0')

        self.assertEquals(len(reactor.connect), 1)
        self.assertEquals(reactor.connect[0][0], "example.com")
        self.assertEquals(reactor.connect[0][1], 80)

        factory = reactor.connect[0][2]
        self.assertIsInstance(factory, ProxyClientFactory)
        self.assertEquals(factory.command, method)
        self.assertEquals(factory.version, 'HTTP/1.0')
        self.assertEquals(factory.headers, {'host': 'example.com'})
        self.assertEquals(factory.data, data)
        self.assertEquals(factory.rest, expectedURI)
        self.assertEquals(factory.father, request)


    def test_process(self):
        """
        L{ProxyRequest.process} should create a connection to the given server,
        with a L{ProxyClientFactory} as connection factory, with the correct
        parameters:
            - forward comment, version and data values
            - update headers with the B{host} value
            - remove the host from the URL
            - pass the request as parent request
        """
        return self._testProcess("/foo/bar", "/foo/bar")


    def test_processWithoutTrailingSlash(self):
        """
        If the incoming request doesn't contain a slash,
        L{ProxyRequest.process} should add one when instantiating
        L{ProxyClientFactory}.
        """
        return self._testProcess("", "/")


    def test_processWithData(self):
        """
        L{ProxyRequest.process} should be able to retrieve request body and
        to forward it.
        """
        return self._testProcess(
            "/foo/bar", "/foo/bar", "POST", "Some content")


    def test_processWithPort(self):
        """
        Check that L{ProxyRequest.process} correctly parse port in the incoming
        URL, and create a outgoing connection with this port.
        """
        transport = StringTransportWithDisconnection()
        channel = DummyChannel(transport)
        reactor = FakeReactor()
        request = ProxyRequest(channel, False, reactor)
        request.gotLength(0)
        request.requestReceived('GET', 'http://example.com:1234/foo/bar',
                                'HTTP/1.0')

        # That should create one connection, with the port parsed from the URL
        self.assertEquals(len(reactor.connect), 1)
        self.assertEquals(reactor.connect[0][0], "example.com")
        self.assertEquals(reactor.connect[0][1], 1234)



class DummyFactory(object):
    """
    A simple holder for C{host} and C{port} information.
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port



class ReverseProxyRequestTestCase(TestCase):
    """
    Tests for L{ReverseProxyRequest}.
    """

    def test_process(self):
        """
        L{ReverseProxyRequest.process} should create a connection to its
        factory host/port, using a L{ProxyClientFactory} instantiated with the
        correct parameters, and particulary set the B{host} header to the
        factory host.
        """
        transport = StringTransportWithDisconnection()
        channel = DummyChannel(transport)
        reactor = FakeReactor()
        request = ReverseProxyRequest(channel, False, reactor)
        request.factory = DummyFactory("example.com", 1234)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')

        # Check that one connection has been created, to the good host/port
        self.assertEquals(len(reactor.connect), 1)
        self.assertEquals(reactor.connect[0][0], "example.com")
        self.assertEquals(reactor.connect[0][1], 1234)

        # Check the factory passed to the connect, and its headers
        factory = reactor.connect[0][2]
        self.assertIsInstance(factory, ProxyClientFactory)
        self.assertEquals(factory.headers, {'host': 'example.com'})
