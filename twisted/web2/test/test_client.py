from twisted.python import failure

from twisted.internet import protocol, interfaces, defer

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
        for header in resp.headers.getAllRawHeaders():
            self.assertIn(header, expectedHeaders)


class TestHTTPClient(ClientTests):
    def test_simpleRequest(self):
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        def gotData(data):
            self.assertEquals(data, '1234567890')

        def gotResp(resp):
            self.assertEquals(resp.code, 200)

            self.assertHeaders(resp, (('Content-Length', ['10']),))

            return defer.maybeDeferred(resp.stream.read).addCallback(gotData)
                
        d = cxn.client.submitRequest(req).addCallback(gotResp)

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                                 ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Content-Length: 10',
                              'Connection: close',
                              '',
                              '1234567890'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_delayedContent(self):
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        def gotData(data):
            self.assertEquals(data, '1234567890')

        def gotResp(resp):
            self.assertEquals(resp.code, 200)
            self.assertHeaders(resp, (('Content-Length', ['10']),))

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
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        req2 = http.ClientRequest('GET', '/bar', None, None)

        def gotResp(resp):
            self.assertEquals(resp.code, 200)

            self.assertHeaders(resp, (('Content-Length', ['0']),))

        d = cxn.client.submitRequest(req, closeAfter=False).addCallback(gotResp)

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
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/',
                                 {'Accept-Language': {'en': 1.0}}, None)

        def gotResp(resp):
            self.assertEquals(resp.code, 200)

            self.assertHeaders(resp, (('Content-Length', ['0']),
                                      ('Connection', ['Keep-Alive'])))

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

        d = cxn.client.submitRequest(req, closeAfter=False).addCallback(gotResp)

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                            ['Connection: Keep-Alive',
                             'Accept-Language: en'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Content-Length: 0',
                              'Connection: Keep-Alive',
                              '\r\n'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_streamedUpload(self):
        cxn = self.connect(inputTimeOut=None)

        req = http.ClientRequest('PUT', '/foo', None, 'Helloooo content')

        def gotResp(resp):
            self.assertEquals(resp.code, 202)
            
        d = cxn.client.submitRequest(req).addCallback(gotResp)

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
        cxn = self.connect(inputTimeOut=None)
            
        req = http.ClientRequest('HEAD', '/', None, None)

        def gotData(data):
            self.assertEquals(data, None)

        def gotResp(resp):
            self.assertEquals(resp.code, 200)
            
            return defer.maybeDeferred(resp.stream.read).addCallback(gotData)

        d = cxn.client.submitRequest(req).addCallback(gotResp)

        self.assertReceived(cxn, 'HEAD / HTTP/1.1',
                            ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              'Connection: close',
                              '',
                              'Pants')) # bad server

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_chunkedUpload(self):
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
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        def gotResp(resp):
            self.assertEquals(resp.code, 200)
            
            self.failIf(('Connection', ['close']) in resp.headers.getAllRawHeaders())
            
        d = cxn.client.submitRequest(req).addCallback(gotResp)

        self.assertReceived(cxn, 'GET / HTTP/1.1',
                            ['Connection: close'])

        self.writeLines(cxn, ('HTTP/1.1 200 OK',
                              '',
                              'Some Content'))

        return d.addCallback(lambda _: self.assertDone(cxn))

    def test_serverIsntHttp(self):
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        def gotResp(r):
            print r

        d = cxn.client.submitRequest(req).addCallback(gotResp)
        
        self.assertFailure(d, http.ProtocolError)

        self.writeLines(cxn, ('HTTP-NG/1.1 200 OK',
                              '\r\n'))


    def test_oldServer(self):
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req)

        self.assertFailure(d, http.ProtocolError)

        self.writeLines(cxn, ('HTTP/2.3 200 OK',
                              '\r\n'))


    def test_shortStatus(self):
        cxn = self.connect(inputTimeOut=None)
        req = http.ClientRequest('GET', '/', None, None)

        d = cxn.client.submitRequest(req)

        self.assertFailure(d, http.ProtocolError)

        self.writeLines(cxn, ('HTTP/1.1 200',
                              '\r\n'))

    def test_errorReadingRequestStream(self):
        cxn = self.connect(inputTimeOut=None)
        
        s = stream.ProducerStream()
        s.write('Foo')
        
        req = http.ClientRequest('GET', '/', None, s)

        d = cxn.client.submitRequest(req)

        self.assertFailure(d, IOError)

        s.finish(IOError('Test Error'))

        return d

