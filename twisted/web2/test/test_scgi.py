from twisted.trial import unittest

from twisted.internet import defer
from twisted.internet.address import IPv4Address

from twisted.web2.test.test_http import LoopbackRelay, TestConnection
from twisted.web2.test.test_http import TestClient, HTTPTests, TestRequest

from twisted.web2.test.test_client import TestServer, ClientTests
from twisted.web2.test.test_server import SimpleRequest

from twisted.web2 import server
from twisted.web2 import http_headers
from twisted.web2 import stream
from twisted.web2 import twscgi

def parseSCGIHeaders(headers):
    return zip(*[iter(headers.split(':', 1)[1].split('\x00'))]*2)

class SCGITests(HTTPTests):
    def connect(self, logFile=None):
        cxn = TestConnection()
        cxn.client = self.clientProtocol
        cxn.server = self.serverProtocol
        
        cxn.serverToClient = LoopbackRelay(cxn.client, logFile)
        cxn.clientToServer = LoopbackRelay(cxn.server, logFile)
        cxn.server.makeConnection(cxn.serverToClient)
        cxn.client.makeConnection(cxn.clientToServer)

        return cxn

        
class SCGIClientTests(SCGITests, ClientTests):
    def setUp(self):
        self.serverProtocol = TestServer()

    def doTestSCGI(self, request):
        if request.stream.length is None:
            return http.Response(responsecode.LENGTH_REQUIRED)
        factory = twscgi.SCGIClientProtocolFactory(request)
        self.clientProtocol = factory.buildProtocol(None)
        self.cxn = self.connect()
        return factory.deferred

    def testSimpleRequest(self):
        def gotResponse(resp):
            self.assertEquals(resp.code, 200)
            self.assertEquals(resp.headers.getHeader('Content-Type'), 
                              http_headers.MimeType.fromString('text/plain'))

            return defer.maybeDeferred(resp.stream.read
                                       ).addCallback(self.assertEquals, '42')
            
        req = SimpleRequest(None, 'GET', '/')

        d = self.doTestSCGI(req)
        d.addCallback(gotResponse)

        self.iterate(self.cxn)

        headers = parseSCGIHeaders(self.cxn.server.data)

        self.assertEquals(headers[0], ('CONTENT_LENGTH', '0'))

        self.failUnlessIn(('SCGI', '1'), headers)
        
        self.writeLines(self.cxn, ['Status: 200 OK',
                                   'Content-Type: text/plain',
                                   'Content-Length: 2',
                                   '',
                                   '42'])

        return d

    def testOperatesOnStreamDirectly(self):
        def gotResponse(resp):
            self.assertEquals(resp.code, 200)
            self.assertEquals(resp.headers.getHeader('Content-Type'), 
                              http_headers.MimeType.fromString('text/plain'))
            
            stream = resp.stream
            resp.stream = None

            return defer.maybeDeferred(stream.read
                                       ).addCallback(self.assertEquals, '42')
            
        req = SimpleRequest(None, 'GET', '/')

        d = self.doTestSCGI(req)
        d.addCallback(gotResponse)

        self.iterate(self.cxn)

        headers = parseSCGIHeaders(self.cxn.server.data)

        self.assertEquals(headers[0], ('CONTENT_LENGTH', '0'))

        self.failUnlessIn(('SCGI', '1'), headers)
        
        self.writeLines(self.cxn, ['Status: 200 OK',
                                   'Content-Type: text/plain',
                                   'Content-Length: 2',
                                   '',
                                   '42'])
        
        return d
