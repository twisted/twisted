from __future__ import nested_scopes

import time, sys
from twisted.trial import unittest
from twisted.trial.util import wait, spinUntil
from twisted.web2 import http, http_headers, responsecode, error, iweb, stream

from twisted.internet import reactor, protocol, address, interfaces, utils
from twisted.internet import defer
from twisted.protocols import loopback
from twisted.python import util
from zope.interface import implements


class PreconditionTestCase(unittest.TestCase):
    def checkPreconditions(self, request, headers, expectedResult, expectedCode,
                           initCode=responsecode.OK, entityExists=True):
        response = TestResponse()
        code=response.code=initCode
        preconditionsPass = True
        response.headers = headers
        
        try:
            http.checkPreconditions(request, response, entityExists=entityExists)
        except http.HTTPError, e:
            preconditionsPass = False
            code = e.response.code
        self.assertEquals(preconditionsPass, expectedResult)
        self.assertEquals(code, expectedCode)

    def testWithoutHeaders(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        out_headers = http_headers.Headers()
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)
        
        out_headers.removeHeader("ETag")
        out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)
        
    def testIfMatch(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        out_headers = http_headers.Headers()

        # Behavior with no ETag set, should be same as with an ETag
        request.headers.setRawHeaders("If-Match", ('*',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED, entityExists=False)
        
        # Ask for tag, but no etag set.
        request.headers.setRawHeaders("If-Match", ('"frob"',))
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)

        ## Actually set the ETag header
        out_headers.setHeader("ETag", http_headers.ETag('foo'))
        out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT

        # behavior of entityExists
        request.headers.setRawHeaders("If-Match", ('*',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED, entityExists=False)

        # tag matches
        request.headers.setRawHeaders("If-Match", ('"frob", "foo"',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        # none match
        request.headers.setRawHeaders("If-Match", ('"baz", "bob"',))
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, out_headers, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)
        
        # Must only compare strong tags
        out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.headers.setRawHeaders("If-Match", ('W/"foo"',))
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)

    def testIfUnmodifiedSince(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        out_headers = http_headers.Headers()
        
        # No Last-Modified => always fail.
        request.headers.setRawHeaders("If-Unmodified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)

        # Set output headers
        out_headers.setHeader("ETag", http_headers.ETag('foo'))
        out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT

        request.headers.setRawHeaders("If-Unmodified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)
        
        request.headers.setRawHeaders("If-Unmodified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, out_headers, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)

        # invalid date => header ignored
        request.headers.setRawHeaders("If-Unmodified-Since", ('alalalalalalalalalala',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)


    def testIfModifiedSince(self):
        if time.time() < 946771200:
            raise "Your computer's clock is way wrong, this test will be invalid."

        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        out_headers = http_headers.Headers()
        
        # No Last-Modified => always succeed
        request.headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        # Set output headers
        out_headers.setHeader("ETag", http_headers.ETag('foo'))
        out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        
        request.headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, False, responsecode.NOT_MODIFIED)
        
        request.headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, out_headers, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)

        # invalid date => header ignored
        request.headers.setRawHeaders("If-Modified-Since", ('alalalalalalalalalala',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        # date in the future => assume modified
        request.headers.setHeader("If-Modified-Since", time.time() + 500)
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

    def testIfNoneMatch(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        out_headers = http_headers.Headers()
        
        request.headers.setRawHeaders("If-None-Match", ('"foo"',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)
        
        out_headers.setHeader("ETag", http_headers.ETag('foo'))
        out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        
        # behavior of entityExists
        request.headers.setRawHeaders("If-None-Match", ('*',))
        request.method="PUT"
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, out_headers, False, responsecode.NOT_MODIFIED)
        self.checkPreconditions(request, out_headers, True, responsecode.OK, entityExists=False)

        # tag matches
        request.headers.setRawHeaders("If-None-Match", ('"frob", "foo"',))
        request.method="PUT"
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, out_headers, False, responsecode.NOT_MODIFIED)

        # now with IMS, also:
        request.headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        request.method="PUT"
        self.checkPreconditions(request, out_headers, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, out_headers, False, responsecode.NOT_MODIFIED)
        
        request.headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        request.headers.removeHeader("If-Modified-Since")
        
        
        # none match
        request.headers.setRawHeaders("If-None-Match", ('"baz", "bob"',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        # now with IMS, also:
        request.headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)
        
        request.headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)

        request.headers.removeHeader("If-Modified-Since")

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, out_headers, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)
        
        # Weak tags okay for GET
        out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.headers.setRawHeaders("If-None-Match", ('W/"foo"',))
        self.checkPreconditions(request, out_headers, False, responsecode.NOT_MODIFIED)

        # Weak tags not okay for other methods
        request.method="PUT"
        out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.headers.setRawHeaders("If-None-Match", ('W/"foo"',))
        self.checkPreconditions(request, out_headers, True, responsecode.OK)


class IfRangeTestCase(unittest.TestCase):
    def testIfRange(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        response = TestResponse()
        
        self.assertEquals(http.checkIfRange(request, response), True)

        request.headers.setRawHeaders("If-Range", ('"foo"',))
        self.assertEquals(http.checkIfRange(request, response), False)
        
        response.headers.setHeader("ETag", http_headers.ETag('foo'))
        self.assertEquals(http.checkIfRange(request, response), True)

        request.headers.setRawHeaders("If-Range", ('"bar"',))
        response.headers.setHeader("ETag", http_headers.ETag('foo'))
        self.assertEquals(http.checkIfRange(request, response), False)

        request.headers.setRawHeaders("If-Range", ('W/"foo"',))
        response.headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        self.assertEquals(http.checkIfRange(request, response), False)

        request.headers.setRawHeaders("If-Range", ('"foo"',))
        response.headers.removeHeader("ETag")
        self.assertEquals(http.checkIfRange(request, response), False)

        request.headers.setRawHeaders("If-Range", ('Sun, 02 Jan 2000 00:00:00 GMT',))
        response.headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.assertEquals(http.checkIfRange(request, response), True)

        request.headers.setRawHeaders("If-Range", ('Sun, 02 Jan 2000 00:00:01 GMT',))
        response.headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.assertEquals(http.checkIfRange(request, response), False)

        request.headers.setRawHeaders("If-Range", ('Sun, 01 Jan 2000 23:59:59 GMT',))
        response.headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.assertEquals(http.checkIfRange(request, response), False)

        request.headers.setRawHeaders("If-Range", ('Sun, 01 Jan 2000 23:59:59 GMT',))
        response.headers.removeHeader("Last-Modified")
        self.assertEquals(http.checkIfRange(request, response), False)
        
        request.headers.setRawHeaders("If-Range", ('jwerlqjL#$Y*KJAN',))
        self.assertEquals(http.checkIfRange(request, response), False)
    


class LoopbackRelay(loopback.LoopbackRelay):
    implements(interfaces.IProducer)
    
    def pauseProducing(self):
        self.paused = True
        
    def resumeProducing(self):
        self.paused = False

    def stopProducing(self):
        self.loseConnection()

    def halfCloseConnection(self, read=False, write=False):
        # HACK.
        if write:
            self.loseConnection()

class TestRequest(http.Request):
    def process(self):
        self.cmds = []
        self.cmds.append(('init', self.method, self.uri, self.clientproto, tuple(self.headers.getAllRawHeaders())))
        
    def handleContentChunk(self, data):
        self.cmds.append(('contentChunk', data))
        
    def handleContentComplete(self):
        self.cmds.append(('contentComplete',))
        
    def connectionLost(self, reason):
        self.cmds.append(('connectionLost', reason))

class TestResponse(object):
    implements(iweb.IResponse)
    
    code = responsecode.OK
    data = ""
    headers = None
    consumer = None
    
    def __init__(self, initialData=None):
        self.headers = http_headers.Headers()
        self.callback = defer.Deferred()
        self.stream = stream.ProducerStream()
        
    def write(self, data):
        self.stream.write(data)

    def finish(self):
        self.stream.finish()
        
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

    def loseConnection(self):
        self.done = True
        self.transport.loseConnection()

class TestConnection:
    def __init__(self):
        self.requests = []
        self.client = None

class HTTPTests(unittest.TestCase):
    def connect(self, logFile=None, maxPipeline=4, timeOut=60000):
        cxn = TestConnection()

        def makeTestRequest(*args):
            cxn.requests.append(TestRequest(*args))
            return cxn.requests[-1]
        
        factory = http.HTTPFactory()
        factory.requestFactory = makeTestRequest
        factory.maxPipeline = maxPipeline
        factory.timeOut = timeOut
        
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

    def assertDone(self, cxn, done=True):
        self.iterate(cxn)
        self.assertEquals(cxn.client.done, done)
        

class CoreHTTPTestCase(HTTPTests):
    # Note: these tests compare the client output using string
    #       matching. It is acceptable for this to change and break
    #       the test if you know what you are doing.
    
    def testHTTP0_9(self, nouri=False):
        cxn = self.connect()
        cmds = [[]]
        data = ""

        if nouri:
            cxn.client.write("GET\r\n")
        else:
            cxn.client.write("GET /\r\n")
        # Second request which should not be handled
        cxn.client.write("GET /two\r\n")
        
        cmds[0] += [('init', 'GET', '/', (0,9), ()), ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        response = TestResponse()
        response.headers.setRawHeaders("Yo", ("One", "Two"))
        cxn.requests[0].writeResponse(response)
        response.write("")
        
        self.compareResult(cxn, cmds, data)
        
        response.write("Output")
        data += "Output"
        self.compareResult(cxn, cmds, data)
        
        response.finish()
        self.compareResult(cxn, cmds, data)
        
        self.assertDone(cxn)

    def testHTTP0_9_nouri(self):
        self.testHTTP0_9(True)
        
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

        response = TestResponse()
        response.headers.setRawHeaders("Yo", ("One", "Two"))
        cxn.requests[0].writeResponse(response)
        response.write("")
        
        data += "HTTP/1.1 200 OK\r\nYo: One\r\nYo: Two\r\nConnection: close\r\n\r\n"
        self.compareResult(cxn, cmds, data)
        
        response.write("Output")
        data += "Output"
        self.compareResult(cxn, cmds, data)
        
        response.finish()
        self.compareResult(cxn, cmds, data)
        
        self.assertDone(cxn)

    def testHTTP1_0_keepalive(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""

        cxn.client.write("GET / HTTP/1.0\r\nConnection: keep-alive\r\nContent-Length: 5\r\nHost: localhost\r\n\r\nInput")
        cxn.client.write("GET /two HTTP/1.0\r\n\r\n")
        # Third request shouldn't be handled
        cxn.client.write("GET /three HTTP/1.0\r\n\r\n")
        
        cmds[0] += [('init', 'GET', '/', (1,0),
                     (('Content-Length', ['5']), ('Host', ['localhost']),)),
                    ('contentChunk', 'Input'),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        response0 = TestResponse()
        response0.headers.setRawHeaders("Content-Length", ("6", ))
        response0.headers.setRawHeaders("Yo", ("One", "Two"))
        cxn.requests[0].writeResponse(response0)
        response0.write("")
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 6\r\nYo: One\r\nYo: Two\r\nConnection: Keep-Alive\r\n\r\n"
        self.compareResult(cxn, cmds, data)
        
        response0.write("Output")
        data += "Output"
        self.compareResult(cxn, cmds, data)
        
        response0.finish()
        
        # Now for second request:
        cmds.append([])
        cmds[1] += [('init', 'GET', '/two', (1,0), ()),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        
        response1 = TestResponse()
        response1.headers.setRawHeaders("Content-Length", ("0", ))
        cxn.requests[1].writeResponse(response1)
        response1.write("")
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        self.compareResult(cxn, cmds, data)
        response1.finish()
        
        self.assertDone(cxn)

    def testHTTP1_1_pipelining(self):
        cxn = self.connect(maxPipeline=2)
        cmds = []
        data = ""

        # Both these show up immediately.
        cxn.client.write("GET / HTTP/1.1\r\nContent-Length: 5\r\nHost: localhost\r\n\r\nInput")
        cxn.client.write("GET /two HTTP/1.1\r\nHost: localhost\r\n\r\n")
        # Doesn't show up until the first is done.
        cxn.client.write("GET /three HTTP/1.1\r\nHost: localhost\r\n\r\n")
        # Doesn't show up until the second is done.
        cxn.client.write("GET /four HTTP/1.1\r\nHost: localhost\r\n\r\n")

        cmds.append([])
        cmds[0] += [('init', 'GET', '/', (1,1),
                     (('Content-Length', ['5']), ('Host', ['localhost']),)),
                    ('contentChunk', 'Input'),
                    ('contentComplete',)]
        cmds.append([])
        cmds[1] += [('init', 'GET', '/two', (1,1),
                     (('Host', ['localhost']),)),
                    ('contentComplete',)]
        
        self.compareResult(cxn, cmds, data)

        response0 = TestResponse()
        response0.headers.setRawHeaders("Content-Length", ("6", ))
        cxn.requests[0].writeResponse(response0)
        response0.write("")
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\n"
        self.compareResult(cxn, cmds, data)
        
        response0.write("Output")
        data += "Output"
        self.compareResult(cxn, cmds, data)
        
        response0.finish()
        
        # Now the third request gets read:
        cmds.append([])
        cmds[2] += [('init', 'GET', '/three', (1,1),
                     (('Host', ['localhost']),)),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        # Let's write out the third request before the second.
        # This should not cause anything to be written to the client.
        response2 = TestResponse()
        response2.headers.setRawHeaders("Content-Length", ("5", ))
        cxn.requests[2].writeResponse(response2)
        
        response2.write("Three")
        response2.finish()
        
        self.compareResult(cxn, cmds, data)
        
        response1 = TestResponse()
        response1.headers.setRawHeaders("Content-Length", ("3", ))
        cxn.requests[1].writeResponse(response1)
        response1.write("Two")
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nTwo"
        self.compareResult(cxn, cmds, data)
        
        response1.finish()
        
        # Fourth request shows up
        cmds.append([])
        cmds[3] += [('init', 'GET', '/four', (1,1),
                     (('Host', ['localhost']),)),
                    ('contentComplete',)]
        data += "HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nThree"
        self.compareResult(cxn, cmds, data)
        
        response3 = TestResponse()
        response3.headers.setRawHeaders("Content-Length", ("0",))
        cxn.requests[3].writeResponse(response3)
        response3.finish()
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        self.compareResult(cxn, cmds, data)

        self.assertDone(cxn, done=False)
        cxn.client.loseConnection()
        self.assertDone(cxn)

    def testHTTP1_1_chunking(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""
        cxn.client.write("GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\nHost: localhost\r\n\r\n5\r\nInput\r\n")
        
        cmds[0] += [('init', 'GET', '/', (1,1),
                     (('Host', ['localhost']),)),
                    ('contentChunk', 'Input')]
        
        self.compareResult(cxn, cmds, data)
        
        cxn.client.write("1; blahblahblah\r\na\r\n10\r\nabcdefghijklmnop\r\n")
        cmds[0] += [('contentChunk', 'a'),('contentChunk', 'abcdefghijklmnop')]
        self.compareResult(cxn, cmds, data)
        
        cxn.client.write("0\r\nRandom-Ignored-Trailer: foo\r\n\r\n")
        cmds[0] += [('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        response = TestResponse()
        cxn.requests[0].writeResponse(response)
        response.write("Output")
        data += "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n6\r\nOutput\r\n"
        self.compareResult(cxn, cmds, data)

        response.write("blahblahblah")
        data += "C\r\nblahblahblah\r\n"
        self.compareResult(cxn, cmds, data)

        response.finish()
        data += "0\r\n\r\n"
        self.compareResult(cxn, cmds, data)

        cxn.client.loseConnection()
        self.assertDone(cxn)

    def testHTTP1_1_expect_continue(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""
        cxn.client.write("GET / HTTP/1.1\r\nContent-Length: 5\r\nHost: localhost\r\nExpect: 100-continue\r\n\r\n")
        cmds[0] += [('init', 'GET', '/', (1,1),
                     (('Content-Length', ['5']), ('Host', ['localhost']), ('Expect', ['100-continue'])))]
        self.compareResult(cxn, cmds, data)

        cxn.requests[0].stream.read()
        data += "HTTP/1.1 100 Continue\r\n\r\n"
        self.compareResult(cxn, cmds, data)

        cxn.client.write("Input")
        cmds[0] += [('contentChunk', 'Input'),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        response = TestResponse()
        response.headers.setRawHeaders("Content-Length", ("6",))
        cxn.requests[0].writeResponse(response)
        response.write("Output")
        response.finish()
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nOutput"
        self.compareResult(cxn, cmds, data)
        
        cxn.client.loseConnection()
        self.assertDone(cxn)
        
    def testHeaderContinuation(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""
        
        cxn.client.write("GET / HTTP/1.1\r\nHost: localhost\r\nFoo: yada\r\n yada\r\n\r\n")
        cmds[0] += [('init', 'GET', '/', (1,1),
                     (('Host', ['localhost']), ('Foo', ['yada yada']),)),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)
        
        cxn.client.loseConnection()
        self.assertDone(cxn)

    def testTimeout_immediate(self):
        # timeout 0 => timeout on first iterate call
        cxn = self.connect(timeOut = 0)
        self.assertDone(cxn)

    def testTimeout_inRequest(self):
        cxn = self.connect(timeOut = 0.3)
        cmds = [[]]
        data = ""

        cxn.client.write("GET / HTTP/1.1\r\n")
        time.sleep(0.5)
        self.assertDone(cxn)
        
    def testTimeout_betweenRequests(self):
        cxn = self.connect(timeOut = 0.3)
        cmds = [[]]
        data = ""
        
        cxn.client.write("GET / HTTP/1.1\r\n\r\n")
        cmds[0] += [('init', 'GET', '/', (1,1), ()),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        response = TestResponse()
        response.headers.setRawHeaders("Content-Length", ("0",))
        cxn.requests[0].writeResponse(response)
        response.finish()
        
        data += "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"

        self.compareResult(cxn, cmds, data)
        time.sleep(0.5) # Wait for timeout
        self.assertDone(cxn)

    def testExtraCRLFs(self):
        cxn = self.connect()
        cmds = [[]]
        data = ""
        
        # Some broken clients (old IEs) send an extra CRLF after post
        cxn.client.write("POST / HTTP/1.1\r\nContent-Length: 5\r\nHost: localhost\r\n\r\nInput\r\n")
        cmds[0] += [('init', 'POST', '/', (1,1),
                     (('Content-Length', ['5']), ('Host', ['localhost']))),
                    ('contentChunk', 'Input'),
                    ('contentComplete',)]

        self.compareResult(cxn, cmds, data)
        
        cxn.client.write("GET /two HTTP/1.1\r\n\r\n")
        cmds.append([])
        cmds[1] += [('init', 'GET', '/two', (1,1), ()),
                    ('contentComplete',)]
        self.compareResult(cxn, cmds, data)

        cxn.client.loseConnection()
        self.assertDone(cxn)

class ErrorTestCase(HTTPTests):
    def assertStartsWith(self, first, second, msg=None):
        self.assert_(first.startswith(second), '%r.startswith(%r)' % (first, second))

    def checkError(self, cxn, code):
        self.iterate(cxn)
        self.assertStartsWith(cxn.client.data, "HTTP/1.1 %d "%code)
        self.assert_(cxn.client.data.find("\r\nConnection: close\r\n") != -1)

        self.assertDone(cxn)

    def testChunkingError1(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\nasdf\r\n")

        self.checkError(cxn, 400)

    def testChunkingError2(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nblahblah\r\n")

        self.checkError(cxn, 400)
        
    def testChunkingError3(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n-1\r\nasdf\r\n")

        self.checkError(cxn, 400)
        
    def testTooManyHeaders(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\n")
        cxn.client.write("Foo: Bar\r\n"*5000)

        self.checkError(cxn, 400)

    def testLineTooLong(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\n")
        cxn.client.write("Foo: "+("Bar"*10000))

        self.checkError(cxn, 400)

    def testLineTooLong2(self):
        cxn = self.connect()
        cxn.client.write("GET "+("/Bar")*10000 +" HTTP/1.1\r\n")

        self.checkError(cxn, 414)

    def testNoColon(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\n")
        cxn.client.write("Blahblah\r\n\r\n")

        self.checkError(cxn, 400)

    def testBadRequest(self):
        cxn = self.connect()
        cxn.client.write("GET / more HTTP/1.1\r\n")

        self.checkError(cxn, 400)

    def testWrongProtocol(self):
        cxn = self.connect()
        cxn.client.write("GET / Foobar/1.0\r\n")

        self.checkError(cxn, 400)

    def testBadProtocolVersion(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1\r\n")

        self.checkError(cxn, 400)

    def testBadProtocolVersion2(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/-1.0\r\n")

        self.checkError(cxn, 400)

    def testWrongProtocolVersion(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/2.0\r\n")

        self.checkError(cxn, 505)

    def testUnsupportedTE(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\n")
        cxn.client.write("Transfer-Encoding: blahblahblah, chunked\r\n\r\n")
        self.checkError(cxn, 501)

    def testTEWithoutChunked(self):
        cxn = self.connect()
        cxn.client.write("GET / HTTP/1.1\r\n")
        cxn.client.write("Transfer-Encoding: gzip\r\n\r\n")
        self.checkError(cxn, 400)

class PipelinedErrorTestCase(ErrorTestCase):
    # Make sure that even low level reading errors don't corrupt the data stream,
    # but always wait until their turn to respond.
    
    def connect(self):
        cxn = ErrorTestCase.connect(self)
        cxn.client.write("GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        
        cmds = [[('init', 'GET', '/', (1,1),
                 (('Host', ['localhost']),)),
                ('contentComplete', )]]
        data = ""
        self.compareResult(cxn, cmds, data)
        return cxn
    
    def checkError(self, cxn, code):
        self.iterate(cxn)
        self.assertEquals(cxn.client.data, '')
        
        response = TestResponse()
        response.headers.setRawHeaders("Content-Length", ("0",))
        cxn.requests[0].writeResponse(response)
        response.write('')
        
        data = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        self.iterate(cxn)
        self.assertEquals(cxn.client.data, data)

        # Reset the data so the checkError's startswith test can work right.
        cxn.client.data = ""
        
        response.finish()
        ErrorTestCase.checkError(self, cxn, code)


class SimpleFactory(http.HTTPFactory):
    def buildProtocol(self, addr):
        # Do a bunch of crazy crap just so that the test case can know when the
        # connection is done.
        p = http.HTTPFactory.buildProtocol(self, addr)
        cl = p.connectionLost
        def newCl(reason):
            self.testcase.connlost = True
            return cl(reason)
        p.connectionLost = newCl
        self.conn = p
        return p

class SimpleRequest(http.Request):
    def process(self):
        response = TestResponse()
        if self.uri == "/error":
            response.code=402
        else:
            response.code=404
            response.write("URI %s unrecognized." % self.uri)
        response.finish()
        self.writeResponse(response)
        
    def handleContentChunk(self, data):
        pass
        
    def handleContentComplete(self):
        pass
        
class TCPServerTest(unittest.TestCase):
    def setUp(self):
        factory=SimpleFactory()
        factory.requestFactory = SimpleRequest

        factory.testcase = self
        self.factory = factory
        self.connlost = False
        
        self.socket = reactor.listenTCP(0, factory)
        self.port = self.socket.getHost().port

    def tearDown(self):
        # Make sure the listening port is closed
        wait(defer.maybeDeferred(self.socket.stopListening))

        # And make sure the established connection is, too
        self.factory.conn.transport.loseConnection()
        spinUntil(lambda: self.connlost)
        
    def testBasicWorkingness(self):
        out,err,code = wait(
            utils.getProcessOutputAndValue(sys.executable, args=(util.sibpath(__file__, "simple_client.py"), "basic", str(self.port), "tcp")))
        if code != 0:
            print "Error output: \n", err
        self.assertEquals(code, 0)
        self.assertEquals(out, "HTTP/1.1 402 Payment Required\r\nConnection: close\r\n\r\n")

    def testLingeringClose(self):
        out,err,code = wait(
            utils.getProcessOutputAndValue(sys.executable, args=(util.sibpath(__file__, "simple_client.py"), "lingeringClose", str(self.port), "tcp")))
        if code != 0:
            print "Error output: \n", err
        self.assertEquals(code, 0)
        self.assertEquals(out, "HTTP/1.1 402 Payment Required\r\nConnection: close\r\n\r\n")


certPath = util.sibpath(__file__, "server.pem")
from twisted.internet.ssl import DefaultOpenSSLContextFactory
sCTX = DefaultOpenSSLContextFactory(certPath, certPath)

class SSLServerTest(unittest.TestCase):
    def setUp(self):
        factory=SimpleFactory()
        factory.requestFactory = SimpleRequest

        factory.testcase = self
        self.factory = factory
        self.connlost = False
        
        self.socket = reactor.listenSSL(0, factory, sCTX)
        self.port = self.socket.getHost().port

    def tearDown(self):
        # Make sure the listening port is closed
        wait(defer.maybeDeferred(self.socket.stopListening))

        # And make sure the established connection is, too
        self.factory.conn.transport.loseConnection()
        spinUntil(lambda: self.connlost)
        
    def testBasicWorkingness(self):
        out,err,code = wait(
            utils.getProcessOutputAndValue(sys.executable, args=(util.sibpath(__file__, "simple_client.py"), "basic", str(self.port), "ssl")))
        if code != 0:
            print "Error output: \n", err
        self.assertEquals(code, 0)
        self.assertEquals(out, "HTTP/1.1 402 Payment Required\r\nConnection: close\r\n\r\n")

    def testLingeringClose(self):
        out,err,code = wait(
            utils.getProcessOutputAndValue(sys.executable, args=(util.sibpath(__file__, "simple_client.py"), "lingeringClose", str(self.port), "ssl")))
        if code != 0:
            print "Error output: \n", err
        self.assertEquals(code, 0)
        self.assertEquals(out, "HTTP/1.1 402 Payment Required\r\nConnection: close\r\n\r\n")

