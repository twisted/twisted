from __future__ import nested_scopes

import time
from twisted.trial import unittest
from twisted.web2 import http, http_headers, responsecode, error

from twisted.internet import reactor, protocol, address, interfaces
from twisted.protocols import loopback

from zope.interface import implements


class PreconditionTestCase(unittest.TestCase):
    def checkPreconditions(self, request, expectedResult, expectedCode,
                           initCode=responsecode.OK, entityExists=True):
        code=initCode
        request.setResponseCode(code)
        preconditionsPass = True
        
        try:
            request.checkPreconditions(entityExists=entityExists)
        except error.Error, e:
            preconditionsPass = False
            code = e.code
        self.assertEquals(preconditionsPass, expectedResult)
        self.assertEquals(code, expectedCode)

    def testWithoutHeaders(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.out_headers.removeHeader("ETag")
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.checkPreconditions(request, True, responsecode.OK)

        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.checkPreconditions(request, True, responsecode.OK)
        
    def testIfMatch(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())

        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT

        # behavior of entityExists
        request.in_headers.setRawHeaders("If-Match", ('*',))
        self.checkPreconditions(request, True, responsecode.OK)
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED, entityExists=False)

        # tag matches
        request.in_headers.setRawHeaders("If-Match", ('"frob", "foo"',))
        self.checkPreconditions(request, True, responsecode.OK)

        # none match
        request.in_headers.setRawHeaders("If-Match", ('"baz", "bob"',))
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)
        
        # Must only compare strong tags
        request.out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.in_headers.setRawHeaders("If-Match", ('W/"foo"',))
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)

        
    def testIfUnmodifiedSince(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT

        request.in_headers.setRawHeaders("If-Unmodified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.in_headers.setRawHeaders("If-Unmodified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)

        # invalid date => header ignored
        request.in_headers.setRawHeaders("If-Unmodified-Since", ('alalalalalalalalalala',))
        self.checkPreconditions(request, True, responsecode.OK)


    def testIfModifiedSince(self):
        if time.time() < 946771200:
            raise "Your computer's clock is way wrong, this test will be invalid."
        
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)

        # invalid date => header ignored
        request.in_headers.setRawHeaders("If-Modified-Since", ('alalalalalalalalalala',))
        self.checkPreconditions(request, True, responsecode.OK)

        # date in the future => assume modified
        request.in_headers.setHeader("If-Modified-Since", time.time() + 500)
        self.checkPreconditions(request, True, responsecode.OK)

    def testIfNoneMatch(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        
        # behavior of entityExists
        request.in_headers.setRawHeaders("If-None-Match", ('*',))
        request.method="PUT"
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)
        self.checkPreconditions(request, True, responsecode.OK, entityExists=False)

        # tag matches
        request.in_headers.setRawHeaders("If-None-Match", ('"frob", "foo"',))
        request.method="PUT"
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)

        # now with IMS, also:
        request.in_headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        request.method="PUT"
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)

        request.in_headers.removeHeader("If-Modified-Since")
        
        
        # none match
        request.in_headers.setRawHeaders("If-None-Match", ('"baz", "bob"',))
        self.checkPreconditions(request, True, responsecode.OK)

        # now with IMS, also:
        request.in_headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)

        request.in_headers.removeHeader("If-Modified-Since")

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)
        
        # Weak tags okay for GET
        request.out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.in_headers.setRawHeaders("If-None-Match", ('W/"foo"',))
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)

        # Weak tags not okay for other methods
        request.method="PUT"
        request.out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.in_headers.setRawHeaders("If-None-Match", ('W/"foo"',))
        self.checkPreconditions(request, True, responsecode.OK)


class IfRangeTestCase(unittest.TestCase):
    def testIfRange(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())

        request.in_headers.setRawHeaders("If-Range", ('"foo"',))
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.assertEquals(request.checkIfRange(), True)

        request.in_headers.setRawHeaders("If-Range", ('"bar"',))
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.assertEquals(request.checkIfRange(), False)

        request.in_headers.setRawHeaders("If-Range", ('W/"foo"',))
        request.out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        self.assertEquals(request.checkIfRange(), False)

        request.in_headers.setRawHeaders("If-Range", ('"foo"',))
        request.out_headers.removeHeader("ETag")
        self.assertEquals(request.checkIfRange(), False)

        request.in_headers.setRawHeaders("If-Range", ('Sun, 02 Jan 2000 00:00:00 GMT',))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.assertEquals(request.checkIfRange(), True)

        request.in_headers.setRawHeaders("If-Range", ('Sun, 02 Jan 2000 00:00:01 GMT',))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.assertEquals(request.checkIfRange(), False)

        request.in_headers.setRawHeaders("If-Range", ('Sun, 01 Jan 2000 23:59:59 GMT',))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.assertEquals(request.checkIfRange(), False)

        request.in_headers.setRawHeaders("If-Range", ('Sun, 01 Jan 2000 23:59:59 GMT',))
        request.out_headers.removeHeader("Last-Modified")
        self.assertEquals(request.checkIfRange(), False)
        
        request.in_headers.setRawHeaders("If-Range", ('jwerlqjL#$Y*KJAN',))
        self.assertEquals(request.checkIfRange(), False)
    


class LoopbackRelay(loopback.LoopbackRelay):
    implements(interfaces.IProducer)
    
    def pauseProducing(self):
        self.paused = True
        
    def resumeProducing(self):
        self.paused = False

    def stopProducing(self):
        self.loseConnection()


class TestRequest(http.Request):
    def process(self):
        self.cmds = []
        self.cmds.append(('init', self.method, self.uri, self.clientproto, tuple(self.in_headers.getAllRawHeaders())))
        
    def handleContentChunk(self, data):
        self.cmds.append(('contentChunk', data))
        
    def handleContentComplete(self):
        self.cmds.append(('contentComplete',))
        
    def connectionLost(self, reason):
        print "server connection lost"
        self.cmds.append(('connectionLost', reason))
        
class TestClient(protocol.Protocol):
    data = ""
    done = False
    
    def dataReceived(self, data):
        self.data+=data
        
    def write(self, data):
        self.transport.write(data)

    def connectionLost(self, reason):
        self.done = True
        self.transport.loseConnection()
        

class TestConnection:
    def __init__(self):
        self.requests = []
        self.client = None

class CoreHTTPTestCase(unittest.TestCase):
    def connect(self, logFile=None):
        cxn = TestConnection()

        def makeTestRequest(*args):
            cxn.requests.append(TestRequest(*args))
            return cxn.requests[-1]
        
        factory = http.HTTPFactory()
        factory.requestFactory = makeTestRequest
        
        cxn.client = TestClient()
        cxn.server = factory.buildProtocol(address.IPv4Address('TCP', '127.0.0.1', 2345))
        
        cxn.serverToClient = LoopbackRelay(cxn.client, logFile)
        cxn.clientToServer = LoopbackRelay(cxn.server, logFile)
        cxn.server.makeConnection(cxn.serverToClient)
        cxn.client.makeConnection(cxn.clientToServer)

        return cxn

    def iterate(self, cxn):
        reactor.iterate(0)
        cxn.serverToClient.clearBuffer()
        cxn.clientToServer.clearBuffer()
        if cxn.serverToClient.shouldLose:
            cxn.serverToClient.clearBuffer()
        if cxn.clientToServer.shouldLose:
            cxn.clientToServer.clearBuffer()

    def compareResult(self, cxn, cmds, data):
        self.iterate(cxn)
        self.assertEquals([req.cmds for req in cxn.requests], cmds)
        self.assertEquals(cxn.client.data, data)

    def assertDone(self, cxn):
        self.iterate(cxn)
        self.assert_(cxn.client.done)
        
    # Note: these tests compare the client output using string
    #       matching. It is acceptable for this to change and break
    #       the test if you know what you are doing.
    
    def testHTTP0_9(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""
        
        cxn.client.write("GET /\r\n")
        # Second request which should not be handled
        cxn.client.write("GET /two\r\n")
        
        cmds[0] += [('init', 'GET', '/', (0,9), ()), ('contentComplete',)]
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].out_headers.setRawHeaders("Yo", ("One", "Two"))
        cxn.requests[0].acceptData()
        cxn.requests[0].write("")
        
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].write("Output")
        data += "Output"
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].finish()
        self.compareResult(cxn, cmds, data)
        
        self.assertDone(cxn)
        
    def testHTTP1_0(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""

        cxn.client.write("GET / HTTP/1.0\r\nContent-Length: 5\r\nHost: localhost\r\n\r\nInput")
        # Second request which should not be handled
        cxn.client.write("GET /two HTTP/1.0\r\n\r\n")
        
        cmds[0] += [('init', 'GET', '/', (1,0),
                     (('Content-Length', ['5']), ('Host', ['localhost']),)),
                    ('contentChunk', 'Input'),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].out_headers.setRawHeaders("Yo", ("One", "Two"))
        cxn.requests[0].acceptData()
        cxn.requests[0].write("")
        
        data +="HTTP/1.1 200 OK\r\nYo: One\r\nYo: Two\r\nConnection: close\r\n\r\n"
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].write("Output")
        data += "Output"
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].finish()
        self.compareResult(cxn, cmds, data)
        
        self.assertDone(cxn)

    def testHTTP1_0_keepalive(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""

        cxn.client.write("GET / HTTP/1.0\r\nConnection: keep-alive\r\nContent-Length: 5\r\nHost: localhost\r\n\r\nInput")
        cxn.client.write("GET /two HTTP/1.0\r\n\r\n")
        
        cmds[0] += [('init', 'GET', '/', (1,0),
                     (('Content-Length', ['5']), ('Host', ['localhost']),)),
                    ('contentChunk', 'Input'),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].out_headers.setRawHeaders("Content-Length", ("6", ))
        cxn.requests[0].out_headers.setRawHeaders("Yo", ("One", "Two"))
        cxn.requests[0].acceptData()
        cxn.requests[0].write("")
        
        data +="HTTP/1.1 200 OK\r\nContent-Length: 6\r\nYo: One\r\nYo: Two\r\nConnection: Keep-Alive\r\n\r\n"
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].write("Output")
        data += "Output"
        self.compareResult(cxn, cmds, data)
        
        cxn.requests[0].finish()

        # Now for second request:
        cmds.append([])
        cmds[1] += [('init', 'GET', '/two', (1,0), ()),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        cxn.requests[1].out_headers.setRawHeaders("Content-Length", ("0", ))
        cxn.requests[1].acceptData()
        cxn.requests[1].write("")
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        self.compareResult(cxn, cmds, data)
        cxn.requests[1].finish()
        
        self.assertDone(cxn)
        
