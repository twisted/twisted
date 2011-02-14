# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test for L{twisted.web.proxy}.
"""

from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransportWithDisconnection
from twisted.test.proto_helpers import MemoryReactor

from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.proxy import ReverseProxyResource, ProxyClientFactory
from twisted.web.proxy import ProxyClient, ProxyRequest, ReverseProxyRequest
from twisted.web.test.test_web import DummyRequest


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
        reactor = MemoryReactor()
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
        self.assertEquals(len(reactor.tcpClients), 1)
        self.assertEquals(reactor.tcpClients[0][0], "127.0.0.1")
        self.assertEquals(reactor.tcpClients[0][1], 1234)

        # Check the factory passed to the connect, and its given path
        factory = reactor.tcpClients[0][2]
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
        instance with the same class as the originating resource, forward
        port, host, and reactor values, and update the path value with the
        value passed.
        """
        reactor = MemoryReactor()
        resource = ReverseProxyResource("127.0.0.1", 1234, "/path", reactor)
        child = resource.getChild('foo', None)
        # The child should keep the same class
        self.assertIsInstance(child, ReverseProxyResource)
        self.assertEquals(child.path, "/path/foo")
        self.assertEquals(child.port, 1234)
        self.assertEquals(child.host, "127.0.0.1")
        self.assertIdentical(child.reactor, resource.reactor)


    def test_getChildWithSpecial(self):
        """
        The L{ReverseProxyResource} return by C{getChild} has a path which has
        already been quoted.
        """
        resource = ReverseProxyResource("127.0.0.1", 1234, "/path")
        child = resource.getChild(' /%', None)
        self.assertEqual(child.path, "/path/%20%2F%25")



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

    def _parseOutHeaders(self, content):
        """
        Parse the headers out of some web content.

        @param content: Bytes received from a web server.
        @return: A tuple of (requestLine, headers, body). C{headers} is a dict
            of headers, C{requestLine} is the first line (e.g. "POST /foo ...")
            and C{body} is whatever is left.
        """
        headers, body = content.split('\r\n\r\n')
        headers = headers.split('\r\n')
        requestLine = headers.pop(0)
        return (
            requestLine, dict(header.split(': ') for header in headers), body)


    def makeRequest(self, path):
        """
        Make a dummy request object for the URL path.

        @param path: A URL path, beginning with a slash.
        @return: A L{DummyRequest}.
        """
        return DummyRequest(path)


    def makeProxyClient(self, request, method="GET", headers=None,
                        requestBody=""):
        """
        Make a L{ProxyClient} object used for testing.

        @param request: The request to use.
        @param method: The HTTP method to use, GET by default.
        @param headers: The HTTP headers to use expressed as a dict. If not
            provided, defaults to {'accept': 'text/html'}.
        @param requestBody: The body of the request. Defaults to the empty
            string.
        @return: A L{ProxyClient}
        """
        if headers is None:
            headers = {"accept": "text/html"}
        path = '/' + request.postpath
        return ProxyClient(
            method, path, 'HTTP/1.0', headers, requestBody, request)


    def connectProxy(self, proxyClient):
        """
        Connect a proxy client to a L{StringTransportWithDisconnection}.

        @param proxyClient: A L{ProxyClient}.
        @return: The L{StringTransportWithDisconnection}.
        """
        clientTransport = StringTransportWithDisconnection()
        clientTransport.protocol = proxyClient
        proxyClient.makeConnection(clientTransport)
        return clientTransport


    def assertForwardsHeaders(self, proxyClient, requestLine, headers):
        """
        Assert that C{proxyClient} sends C{headers} when it connects.

        @param proxyClient: A L{ProxyClient}.
        @param requestLine: The request line we expect to be sent.
        @param headers: A dict of headers we expect to be sent.
        @return: If the assertion is successful, return the request body as
            bytes.
        """
        self.connectProxy(proxyClient)
        requestContent = proxyClient.transport.value()
        receivedLine, receivedHeaders, body = self._parseOutHeaders(
            requestContent)
        self.assertEquals(receivedLine, requestLine)
        self.assertEquals(receivedHeaders, headers)
        return body


    def makeResponseBytes(self, code, message, headers, body):
        lines = ["HTTP/1.0 %d %s" % (code, message)]
        for header, values in headers:
            for value in values:
                lines.append("%s: %s" % (header, value))
        lines.extend(['', body])
        return '\r\n'.join(lines)


    def assertForwardsResponse(self, request, code, message, headers, body):
        """
        Assert that C{request} has forwarded a response from the server.

        @param request: A L{DummyRequest}.
        @param code: The expected HTTP response code.
        @param message: The expected HTTP message.
        @param headers: The expected HTTP headers.
        @param body: The expected response body.
        """
        self.assertEquals(request.responseCode, code)
        self.assertEquals(request.responseMessage, message)
        receivedHeaders = list(request.responseHeaders.getAllRawHeaders())
        receivedHeaders.sort()
        expectedHeaders = headers[:]
        expectedHeaders.sort()
        self.assertEquals(receivedHeaders, expectedHeaders)
        self.assertEquals(''.join(request.written), body)


    def _testDataForward(self, code, message, headers, body, method="GET",
                         requestBody="", loseConnection=True):
        """
        Build a fake proxy connection, and send C{data} over it, checking that
        it's forwarded to the originating request.
        """
        request = self.makeRequest('foo')
        client = self.makeProxyClient(
            request, method, {'accept': 'text/html'}, requestBody)

        receivedBody = self.assertForwardsHeaders(
            client, '%s /foo HTTP/1.0' % (method,),
            {'connection': 'close', 'accept': 'text/html'})

        self.assertEquals(receivedBody, requestBody)

        # Fake an answer
        client.dataReceived(
            self.makeResponseBytes(code, message, headers, body))

        # Check that the response data has been forwarded back to the original
        # requester.
        self.assertForwardsResponse(request, code, message, headers, body)

        # Check that when the response is done, the request is finished.
        if loseConnection:
            client.transport.loseConnection()

        # Even if we didn't call loseConnection, the transport should be
        # disconnected.  This lets us not rely on the server to close our
        # sockets for us.
        self.assertFalse(client.transport.connected)
        self.assertEquals(request.finished, 1)


    def test_forward(self):
        """
        When connected to the server, L{ProxyClient} should send the saved
        request, with modifications of the headers, and then forward the result
        to the parent request.
        """
        return self._testDataForward(
            200, "OK", [("Foo", ["bar", "baz"])], "Some data\r\n")


    def test_postData(self):
        """
        Try to post content in the request, and check that the proxy client
        forward the body of the request.
        """
        return self._testDataForward(
            200, "OK", [("Foo", ["bar"])], "Some data\r\n", "POST", "Some content")


    def test_statusWithMessage(self):
        """
        If the response contains a status with a message, it should be
        forwarded to the parent request with all the information.
        """
        return self._testDataForward(
            404, "Not Found", [], "")


    def test_contentLength(self):
        """
        If the response contains a I{Content-Length} header, the inbound
        request object should still only have C{finish} called on it once.
        """
        data = "foo bar baz"
        return self._testDataForward(
            200, "OK", [("Content-Length", [str(len(data))])], data)


    def test_losesConnection(self):
        """
        If the response contains a I{Content-Length} header, the outgoing
        connection is closed when all response body data has been received.
        """
        data = "foo bar baz"
        return self._testDataForward(
            200, "OK", [("Content-Length", [str(len(data))])], data,
            loseConnection=False)


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


    def test_keepaliveNotForwarded(self):
        """
        The proxy doesn't really know what to do with keepalive things from
        the remote server, so we stomp over any keepalive header we get from
        the client.
        """
        headers = {
            "accept": "text/html",
            'keep-alive': '300',
            'connection': 'keep-alive',
            }
        expectedHeaders = headers.copy()
        expectedHeaders['connection'] = 'close'
        del expectedHeaders['keep-alive']
        client = ProxyClient('GET', '/foo', 'HTTP/1.0', headers, '', None)
        self.assertForwardsHeaders(
            client, 'GET /foo HTTP/1.0', expectedHeaders)


    def test_defaultHeadersOverridden(self):
        """
        L{server.Request} within the proxy sets certain response headers by
        default. When we get these headers back from the remote server, the
        defaults are overridden rather than simply appended.
        """
        request = self.makeRequest('foo')
        request.responseHeaders.setRawHeaders('server', ['old-bar'])
        request.responseHeaders.setRawHeaders('date', ['old-baz'])
        request.responseHeaders.setRawHeaders('content-type', ["old/qux"])
        client = self.makeProxyClient(request, headers={'accept': 'text/html'})
        self.connectProxy(client)
        headers = {
            'Server': ['bar'],
            'Date': ['2010-01-01'],
            'Content-Type': ['application/x-baz'],
            }
        client.dataReceived(
            self.makeResponseBytes(200, "OK", headers.items(), ''))
        self.assertForwardsResponse(
            request, 200, 'OK', headers.items(), '')



class ProxyClientFactoryTestCase(TestCase):
    """
    Tests for L{ProxyClientFactory}.
    """

    def test_connectionFailed(self):
        """
        Check that L{ProxyClientFactory.clientConnectionFailed} produces
        a B{501} response to the parent request.
        """
        request = DummyRequest(['foo'])
        factory = ProxyClientFactory('GET', '/foo', 'HTTP/1.0',
                                     {"accept": "text/html"}, '', request)

        factory.clientConnectionFailed(None, None)
        self.assertEquals(request.responseCode, 501)
        self.assertEquals(request.responseMessage, "Gateway error")
        self.assertEquals(
            list(request.responseHeaders.getAllRawHeaders()),
            [("Content-Type", ["text/html"])])
        self.assertEquals(
            ''.join(request.written),
            "<H1>Could not connect</H1>")
        self.assertEquals(request.finished, 1)


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
        reactor = MemoryReactor()
        request = ProxyRequest(channel, False, reactor)
        request.gotLength(len(data))
        request.handleContentChunk(data)
        request.requestReceived(method, 'http://example.com%s' % (uri,),
                                'HTTP/1.0')

        self.assertEquals(len(reactor.tcpClients), 1)
        self.assertEquals(reactor.tcpClients[0][0], "example.com")
        self.assertEquals(reactor.tcpClients[0][1], 80)

        factory = reactor.tcpClients[0][2]
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
        reactor = MemoryReactor()
        request = ProxyRequest(channel, False, reactor)
        request.gotLength(0)
        request.requestReceived('GET', 'http://example.com:1234/foo/bar',
                                'HTTP/1.0')

        # That should create one connection, with the port parsed from the URL
        self.assertEquals(len(reactor.tcpClients), 1)
        self.assertEquals(reactor.tcpClients[0][0], "example.com")
        self.assertEquals(reactor.tcpClients[0][1], 1234)



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
        reactor = MemoryReactor()
        request = ReverseProxyRequest(channel, False, reactor)
        request.factory = DummyFactory("example.com", 1234)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')

        # Check that one connection has been created, to the good host/port
        self.assertEquals(len(reactor.tcpClients), 1)
        self.assertEquals(reactor.tcpClients[0][0], "example.com")
        self.assertEquals(reactor.tcpClients[0][1], 1234)

        # Check the factory passed to the connect, and its headers
        factory = reactor.tcpClients[0][2]
        self.assertIsInstance(factory, ProxyClientFactory)
        self.assertEquals(factory.headers, {'host': 'example.com'})
