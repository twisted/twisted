# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for HTTP client.
"""

from twisted.internet import protocol, defer

from twisted.web2.client import http
from twisted.web2 import http_headers
from twisted.web2 import stream
from twisted.web2.test.test_http import LoopbackRelay, HTTPTests, TestConnection



class TestServer(protocol.Protocol):
    data = ""
    done = False

    def dataReceived(self, data):
        self.data += data

    def write(self, data):
        self.transport.write(data)

    def connectionLost(self, reason):
        self.done = True
        self.transport.loseConnection()

    def loseConnection(self):
        self.done = True
        self.transport.loseConnection()



class ClientTests(HTTPTests):
    def connect(self, logFile=None, maxPipeline=4,
                inputTimeOut=60000, betweenRequestsTimeOut=600000):
        cxn = TestConnection()

        cxn.client = http.HTTPClientProtocol()
        cxn.client.inputTimeOut = inputTimeOut
        cxn.server = TestServer()

        cxn.serverToClient = LoopbackRelay(cxn.client, logFile)
        cxn.clientToServer = LoopbackRelay(cxn.server, logFile)

        cxn.server.makeConnection(cxn.serverToClient)
        cxn.client.makeConnection(cxn.clientToServer)

        return cxn

    def writeToClient(self, cxn, data):
        cxn.server.write(data)
        self.iterate(cxn)

    def writeLines(self, cxn, lines):
        self.writeToClient(cxn, '\r\n'.join(lines))

    def assertReceived(self, cxn, expectedStatus, expectedHeaders,
                       expectedContent=None):
        self.iterate(cxn)

        headers, content = cxn.server.data.split('\r\n\r\n', 1)
        status, headers = headers.split('\r\n', 1)
        headers = headers.split('\r\n')

        # check status line
        self.assertEquals(status, expectedStatus)

        # check headers (header order isn't guraunteed so we use
        # self.assertIn
        for x in headers:
            self.assertIn(x, expectedHeaders)

        if not expectedContent:
            expectedContent = ''

        self.assertEquals(content, expectedContent)

    def assertDone(self, cxn):
        self.iterate(cxn)
        self.assertEquals(cxn.server.done, True, 'Connection not closed.')

    def assertHeaders(self, resp, expectedHeaders):
        headers = list(resp.headers.getAllRawHeaders())
        headers.sort()
        self.assertEquals(headers, expectedHeaders)

    def checkResponse(self, resp, code, headers, length, data):
        """
        Assert various things about a response: http code, headers, stream
        length, and data in stream.
        """
        def gotData(gotdata):
            self.assertEquals(gotdata, data)

        self.assertEquals(resp.code, code)
        self.assertHeaders(resp, headers)
        self.assertEquals(resp.stream.length, length)

        return defer.maybeDeferred(resp.stream.read).addCallback(gotData)



class TestHTTPClient(ClientTests):
    """
    Test that the http client works.
    """

    def test_simpleRequest(self):
        """
        Your basic simple HTTP Request.
        """
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req).addCallback(self.checkResponse, 200, [], 10, '1234567890')

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                                 ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Content-Length: 10',
                              'Connection: close',
                              '',
                              '1234567890'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_delayedContent(self):
        """
        Make sure that the client returns the response object as soon as the
        headers are received, even if the data hasn't arrived yet.
        """

        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        def gotData(data):
            self.assertEquals(data, '1234567890')

        def gotResp(resp):
            self.assertEquals(resp.code, 200)
            self.assertHeaders(resp, [])
            self.assertEquals(resp.stream.length, 10)

            self.writeToClient(cxn, '1234567890')

            return defer.maybeDeferred(resp.stream.read).addCallback(gotData)

        d = cxn.client.submitRequest(req).addCallback(gotResp)


        self.assertReceived(cxn, 'GET / HTTP/1.1',
                            ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Content-Length: 10',
                              'Connection: close',
                              '\r\n'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_prematurePipelining(self):
        """
        Ensure that submitting a second request before it's allowed results
        in an AssertionError.
        """
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        req2 = http.ClientRequest('GET', '/bar', None, None)

        d = cxn.client.submitRequest(req, closeAfter=False).addCallback(
            self.checkResponse, 200, [], 0, None)

        self.assertRaises(AssertionError,
                          cxn.client.submitRequest, req2)

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                            ['Connection: Keep-Alive'])
        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Content-Length: 0',
                              'Connection: close',
                              '\r\n'))

        return d

    def test_userHeaders(self):
        """
        Make sure that headers get through in both directions.
        """

        cxn = self.connect(inputTimeOut=None)

        def submitNext(_):
            headers = http_headers.Headers(
                headers={'Accept-Language': {'en': 1.0}},
                rawHeaders={'X-My-Other-Header': ['socks']})

            req = http.ClientRequest('GET', '/', headers, None)

            cxn.server.data = ''

            d = cxn.client.submitRequest(req, closeAfter=True)

            self.assertReceived(cxn, 'GET / HTTP/1.1',
                                ['Connection: close',
                                 'X-My-Other-Header: socks',
                                 'Accept-Language: en'])

            self.writeLines(cxn, ('HTTP/1.1 200 OK',
                                  'Content-Length: 0',
                                  'Connection: close',
                                  '\r\n'))

            return d

        req = http.ClientRequest('GET', '/',
                                 {'Accept-Language': {'en': 1.0}}, None)

        d = cxn.client.submitRequest(req, closeAfter=False).addCallback(
            self.checkResponse, 200, [('X-Foobar', ['Yes'])], 0, None).addCallback(
            submitNext)

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                            ['Connection: Keep-Alive',
                             'Accept-Language: en'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Content-Length: 0',
                              'X-Foobar: Yes',
                              '\r\n'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_streamedUpload(self):
        """
        Make sure that sending request content works.
        """

        cxn = self.connect(inputTimeOut=None)

        req = http.ClientRequest('PUT', '/foo', None, 'Helloooo content')

        d = cxn.client.submitRequest(req).addCallback(self.checkResponse, 202, [], 0, None)

        self.assertReceived(cxn, 'PUT /foo HTTP/1.1',
                            ['Connection: close',
                             'Content-Length: 16'],
                            'Helloooo content')

        self.writeLines(cxn, ('HTTP/1.1 202 Accepted',
                              'Content-Length: 0',
                              'Connection: close',
                              '\r\n'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_sentHead(self):
        """
        Ensure that HEAD requests work, and return Content-Length.
        """

        cxn = self.connect(inputTimeOut=None)

        req = http.ClientRequest('HEAD', '/', None, None)

        d = cxn.client.submitRequest(req).addCallback(self.checkResponse, 200, [('Content-Length', ['5'])], 0, None)

        self.assertReceived(cxn, 'HEAD / HTTP/1.1',
                            ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Connection: close',
                              'Content-Length: 5',
                              '',
                              'Pants')) # bad server

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_sentHeadKeepAlive(self):
        """
        Ensure that keepalive works right after a HEAD request.
        """

        cxn = self.connect(inputTimeOut=None)

        req = http.ClientRequest('HEAD', '/', None, None)

        didIt = [0]

        def gotData(data):
            self.assertEquals(data, None)

        def gotResp(resp):
            self.assertEquals(resp.code, 200)
            self.assertEquals(resp.stream.length, 0)
            self.assertHeaders(resp, [])

            return defer.maybeDeferred(resp.stream.read).addCallback(gotData)

        def submitRequest(second):
            if didIt[0]:
                return
            didIt[0] = second

            if second:
                keepAlive='close'
            else:
                keepAlive='Keep-Alive'

            cxn.server.data = ''

            d = cxn.client.submitRequest(req, closeAfter=second).addCallback(
                self.checkResponse, 200, [('Content-Length', ['5'])], 0, None)

            self.assertReceived(cxn, 'HEAD / HTTP/1.1',
                                ['Connection: '+ keepAlive])

            self.writeLines(cxn, ('HTTP/1.1 200 OK',
                                  'Connection: '+ keepAlive,
                                  'Content-Length: 5',
                                  '\r\n'))

            return d.addCallback(lambda _: submitRequest(1))

        d = submitRequest(0)

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_chunkedUpload(self):
        """
        Ensure chunked data is correctly decoded on upload.
        """

        cxn = self.connect(inputTimeOut=None)

        data = 'Foo bar baz bax'
        s = stream.ProducerStream(length=None)
        s.write(data)

        req = http.ClientRequest('PUT', '/', None, s)

        d = cxn.client.submitRequest(req)

        s.finish()

        self.assertReceived(cxn, 'PUT / HTTP/1.1',
                            ['Connection: close',
                             'Transfer-Encoding: chunked'],
                            '%X\r\n%s\r\n0\r\n\r\n' % (len(data), data))

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Connection: close',
                              'Content-Length: 0',
                              '\r\n'))

        return d.addCallback(lambda _: self.assertDone(cxn))



class TestEdgeCases(ClientTests):
    def test_serverDoesntSendConnectionClose(self):
        """
        Check that a lost connection is treated as end of response, if we
        requested connection: close, even if the server didn't respond with
        connection: close.
        """

        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req).addCallback(self.checkResponse, 200, [], None, 'Some Content')

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                            ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              '',
                              'Some Content'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_serverIsntHttp(self):
        """
        Check that an error is returned if the server doesn't talk HTTP.
        """

        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        def gotResp(r):
            print r

        d = cxn.client.submitRequest(req).addCallback(gotResp)

        self.assertFailure(d, http.ProtocolError)

        self.writeLines(cxn, ('HTTP-NG/1.1 200 OK',
                              '\r\n'))


    def test_newServer(self):
        """
        Check that an error is returned if the server is a new major version.
        """

        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req)

        self.assertFailure(d, http.ProtocolError)

        self.writeLines(cxn, ('HTTP/2.3 200 OK',
                              '\r\n'))


    def test_shortStatus(self):
        """
        Check that an error is returned if the response line is invalid.
        """

        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req)

        self.assertFailure(d, http.ProtocolError)

        self.writeLines(cxn, ('HTTP/1.1 200',
                              '\r\n'))

    def test_errorReadingRequestStream(self):
        """
        Ensure that stream errors are propagated to the response.
        """

        cxn = self.connect(inputTimeOut=None)

        s = stream.ProducerStream()
        s.write('Foo')

        req = http.ClientRequest('GET', '/', None, s)

        d = cxn.client.submitRequest(req)

        s.finish(IOError('Test Error'))

        return self.assertFailure(d, IOError)


    def test_connectionLost(self):
        """
        Check that closing the connection is propagated to the response
        deferred.
        """
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req)

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                                 ['Connection: close'])
        cxn.client.connectionLost(ValueError("foo"))
        return self.assertFailure(d, ValueError)


    def test_connectionLostAfterHeaders(self):
        """
        Test that closing the connection after headers are sent is propagated
        to the response stream.
        """
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req)

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                                 ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Content-Length: 10',
                              'Connection: close',
                              '\r\n'))
        cxn.client.connectionLost(ValueError("foo"))
        def cb(response):
            return self.assertFailure(response.stream.read(), ValueError)
        d.addCallback(cb)
        return d

