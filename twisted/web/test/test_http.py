# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test HTTP support.
"""

from urlparse import urlparse, urlunsplit, clear_cache
import string, random, urllib, cgi

from twisted.trial import unittest
from twisted.web import http
from twisted.protocols import loopback
from twisted.internet import protocol
from twisted.test.test_protocols import StringIOWithoutClosing


class DateTimeTest(unittest.TestCase):
    """Test date parsing functions."""

    def testRoundtrip(self):
        for i in range(10000):
            time = random.randint(0, 2000000000)
            timestr = http.datetimeToString(time)
            time2 = http.stringToDatetime(timestr)
            self.assertEquals(time, time2)


class OrderedDict:

    def __init__(self, dict):
        self.dict = dict
        self.l = dict.keys()

    def __setitem__(self, k, v):
        self.l.append(k)
        self.dict[k] = v

    def __getitem__(self, k):
        return self.dict[k]

    def items(self):
        result = []
        for i in self.l:
            result.append((i, self.dict[i]))
        return result

    def __getattr__(self, attr):
        return getattr(self.dict, attr)


class DummyHTTPHandler(http.Request):

    def process(self):
        self.headers = OrderedDict(self.headers)
        self.content.seek(0, 0)
        data = self.content.read()
        length = self.getHeader('content-length')
        request = "'''\n"+str(length)+"\n"+data+"'''\n"
        self.setResponseCode(200)
        self.setHeader("Request", self.uri)
        self.setHeader("Command", self.method)
        self.setHeader("Version", self.clientproto)
        self.setHeader("Content-Length", len(request))
        self.write(request)
        self.finish()


class LoopbackHTTPClient(http.HTTPClient):

    def connectionMade(self):
        self.sendCommand("GET", "/foo/bar")
        self.sendHeader("Content-Length", 10)
        self.endHeaders()
        self.transport.write("0123456789")


class HTTP1_0TestCase(unittest.TestCase):

    requests = '''\
GET / HTTP/1.0

GET / HTTP/1.1
Accept: text/html

'''
    requests = string.replace(requests, '\n', '\r\n')

    expected_response = "HTTP/1.0 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.0\015\012Content-length: 13\015\012\015\012'''\012None\012'''\012"

    def test_buffer(self):
        """
        Send requests over a channel and check responses match what is expected.
        """
        b = StringIOWithoutClosing()
        a = http.HTTPChannel()
        a.requestFactory = DummyHTTPHandler
        a.makeConnection(protocol.FileWrapper(b))
        # one byte at a time, to stress it.
        for byte in self.requests:
            a.dataReceived(byte)
        a.connectionLost(IOError("all one"))
        value = b.getvalue()
        self.assertEquals(value, self.expected_response)


class HTTP1_1TestCase(HTTP1_0TestCase):

    requests = '''\
GET / HTTP/1.1
Accept: text/html

POST / HTTP/1.1
Content-Length: 10

0123456789POST / HTTP/1.1
Content-Length: 10

0123456789HEAD / HTTP/1.1

'''
    requests = string.replace(requests, '\n', '\r\n')

    expected_response = "HTTP/1.1 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.1\015\012Content-length: 13\015\012\015\012'''\012None\012'''\012HTTP/1.1 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-length: 21\015\012\015\012'''\01210\0120123456789'''\012HTTP/1.1 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-length: 21\015\012\015\012'''\01210\0120123456789'''\012HTTP/1.1 200 OK\015\012Request: /\015\012Command: HEAD\015\012Version: HTTP/1.1\015\012Content-length: 13\015\012\015\012"

class HTTP1_1_close_TestCase(HTTP1_0TestCase):

    requests = '''\
GET / HTTP/1.1
Accept: text/html
Connection: close

GET / HTTP/1.0

'''

    requests = string.replace(requests, '\n', '\r\n')

    expected_response = "HTTP/1.1 200 OK\015\012Connection: close\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.1\015\012Content-length: 13\015\012\015\012'''\012None\012'''\012"


class HTTP0_9TestCase(HTTP1_0TestCase):

    requests = '''\
GET /
'''
    requests = string.replace(requests, '\n', '\r\n')

    expected_response = "HTTP/1.1 400 Bad Request\r\n\r\n"


class HTTPLoopbackTestCase(unittest.TestCase):

    expectedHeaders = {'request' : '/foo/bar',
                       'command' : 'GET',
                       'version' : 'HTTP/1.0',
                       'content-length' : '21'}
    numHeaders = 0
    gotStatus = 0
    gotResponse = 0
    gotEndHeaders = 0

    def _handleStatus(self, version, status, message):
        self.gotStatus = 1
        self.assertEquals(version, "HTTP/1.0")
        self.assertEquals(status, "200")

    def _handleResponse(self, data):
        self.gotResponse = 1
        self.assertEquals(data, "'''\n10\n0123456789'''\n")

    def _handleHeader(self, key, value):
        self.numHeaders = self.numHeaders + 1
        self.assertEquals(self.expectedHeaders[string.lower(key)], value)

    def _handleEndHeaders(self):
        self.gotEndHeaders = 1
        self.assertEquals(self.numHeaders, 4)

    def testLoopback(self):
        server = http.HTTPChannel()
        server.requestFactory = DummyHTTPHandler
        client = LoopbackHTTPClient()
        client.handleResponse = self._handleResponse
        client.handleHeader = self._handleHeader
        client.handleEndHeaders = self._handleEndHeaders
        client.handleStatus = self._handleStatus
        d = loopback.loopbackAsync(server, client)
        d.addCallback(self._cbTestLoopback)
        return d

    def _cbTestLoopback(self, ignored):
        if not (self.gotStatus and self.gotResponse and self.gotEndHeaders):
            raise RuntimeError(
                "didn't got all callbacks %s"
                % [self.gotStatus, self.gotResponse, self.gotEndHeaders])
        del self.gotEndHeaders
        del self.gotResponse
        del self.gotStatus
        del self.numHeaders


class PRequest:
    """Dummy request for persistence tests."""

    def __init__(self, **headers):
        self.received_headers = headers
        self.headers = {}

    def getHeader(self, k):
        return self.received_headers.get(k, '')

    def setHeader(self, k, v):
        self.headers[k] = v


class PersistenceTestCase(unittest.TestCase):
    """Tests for persistent HTTP connections."""

    ptests = [#(PRequest(connection="Keep-Alive"), "HTTP/1.0", 1, {'connection' : 'Keep-Alive'}),
              (PRequest(), "HTTP/1.0", 0, {'connection': None}),
              (PRequest(connection="close"), "HTTP/1.1", 0, {'connection' : 'close'}),
              (PRequest(), "HTTP/1.1", 1, {'connection': None}),
              (PRequest(), "HTTP/0.9", 0, {'connection': None}),
              ]


    def testAlgorithm(self):
        c = http.HTTPChannel()
        for req, version, correctResult, resultHeaders in self.ptests:
            result = c.checkPersistence(req, version)
            self.assertEquals(result, correctResult)
            for header in resultHeaders.keys():
                self.assertEquals(req.headers.get(header, None), resultHeaders[header])


class ChunkingTestCase(unittest.TestCase):

    strings = ["abcv", "", "fdfsd423", "Ffasfas\r\n",
               "523523\n\rfsdf", "4234"]

    def testChunks(self):
        for s in self.strings:
            self.assertEquals((s, ''), http.fromChunk(''.join(http.toChunk(s))))
        self.assertRaises(ValueError, http.fromChunk, '-5\r\nmalformed!\r\n')

    def testConcatenatedChunks(self):
        chunked = ''.join([''.join(http.toChunk(t)) for t in self.strings])
        result = []
        buffer = ""
        for c in chunked:
            buffer = buffer + c
            try:
                data, buffer = http.fromChunk(buffer)
                result.append(data)
            except ValueError:
                pass
        self.assertEquals(result, self.strings)



class ParsingTestCase(unittest.TestCase):

    def runRequest(self, httpRequest, requestClass, success=1):
        httpRequest = httpRequest.replace("\n", "\r\n")
        b = StringIOWithoutClosing()
        a = http.HTTPChannel()
        a.requestFactory = requestClass
        a.makeConnection(protocol.FileWrapper(b))
        # one byte at a time, to stress it.
        for byte in httpRequest:
            if a.transport.closed:
                break
            a.dataReceived(byte)
        a.connectionLost(IOError("all done"))
        if success:
            self.assertEquals(self.didRequest, 1)
            del self.didRequest
        else:
            self.assert_(not hasattr(self, "didRequest"))

    def testBasicAuth(self):
        testcase = self
        class Request(http.Request):
            l = []
            def process(self):
                testcase.assertEquals(self.getUser(), self.l[0])
                testcase.assertEquals(self.getPassword(), self.l[1])
        for u, p in [("foo", "bar"), ("hello", "there:z")]:
            Request.l[:] = [u, p]
            s = "%s:%s" % (u, p)
            f = "GET / HTTP/1.0\nAuthorization: Basic %s\n\n" % (s.encode("base64").strip(), )
            self.runRequest(f, Request, 0)

    def testTooManyHeaders(self):
        httpRequest = "GET / HTTP/1.0\n"
        for i in range(502):
            httpRequest += "%s: foo\n" % i
        httpRequest += "\n"
        class MyRequest(http.Request):
            def process(self):
                raise RuntimeError, "should not get called"
        self.runRequest(httpRequest, MyRequest, 0)

    def testHeaders(self):
        httpRequest = """\
GET / HTTP/1.0
Foo: bar
baz: 1 2 3

"""
        testcase = self

        class MyRequest(http.Request):
            def process(self):
                testcase.assertEquals(self.getHeader('foo'), 'bar')
                testcase.assertEquals(self.getHeader('Foo'), 'bar')
                testcase.assertEquals(self.getHeader('bAz'), '1 2 3')
                testcase.didRequest = 1
                self.finish()

        self.runRequest(httpRequest, MyRequest)

    def testCookies(self):
        """
        Test cookies parsing and reading.
        """
        httpRequest = '''\
GET / HTTP/1.0
Cookie: rabbit="eat carrot"; ninja=secret; spam="hey 1=1!"

'''
        testcase = self

        class MyRequest(http.Request):
            def process(self):
                testcase.assertEquals(self.getCookie('rabbit'), '"eat carrot"')
                testcase.assertEquals(self.getCookie('ninja'), 'secret')
                testcase.assertEquals(self.getCookie('spam'), '"hey 1=1!"')
                testcase.didRequest = 1
                self.finish()

        self.runRequest(httpRequest, MyRequest)

    def testGET(self):
        httpRequest = '''\
GET /?key=value&multiple=two+words&multiple=more%20words&empty= HTTP/1.0

'''
        testcase = self
        class MyRequest(http.Request):
            def process(self):
                testcase.assertEquals(self.method, "GET")
                testcase.assertEquals(self.args["key"], ["value"])
                testcase.assertEquals(self.args["empty"], [""])
                testcase.assertEquals(self.args["multiple"], ["two words", "more words"])
                testcase.didRequest = 1
                self.finish()

        self.runRequest(httpRequest, MyRequest)


    def test_extraQuestionMark(self):
        """
        While only a single '?' is allowed in an URL, several other servers
        allow several and pass all after the first through as part of the
        query arguments.  Test that we emulate this behavior.
        """
        httpRequest = 'GET /foo?bar=?&baz=quux HTTP/1.0\n\n'

        testcase = self
        class MyRequest(http.Request):
            def process(self):
                testcase.assertEqual(self.method, 'GET')
                testcase.assertEqual(self.path, '/foo')
                testcase.assertEqual(self.args['bar'], ['?'])
                testcase.assertEqual(self.args['baz'], ['quux'])
                testcase.didRequest = 1
                self.finish()

        self.runRequest(httpRequest, MyRequest)


    def testPOST(self):
        query = 'key=value&multiple=two+words&multiple=more%20words&empty='
        httpRequest = '''\
POST / HTTP/1.0
Content-Length: %d
Content-Type: application/x-www-form-urlencoded

%s''' % (len(query), query)

        testcase = self
        class MyRequest(http.Request):
            def process(self):
                testcase.assertEquals(self.method, "POST")
                testcase.assertEquals(self.args["key"], ["value"])
                testcase.assertEquals(self.args["empty"], [""])
                testcase.assertEquals(self.args["multiple"], ["two words", "more words"])
                testcase.didRequest = 1
                self.finish()

        self.runRequest(httpRequest, MyRequest)

    def testMissingContentDisposition(self):
        req = '''\
POST / HTTP/1.0
Content-Type: multipart/form-data; boundary=AaB03x
Content-Length: 103

--AaB03x
Content-Type: text/plain
Content-Transfer-Encoding: quoted-printable

abasdfg
--AaB03x--
'''
        self.runRequest(req, http.Request, success=False)

class QueryArgumentsTestCase(unittest.TestCase):
    def testUnquote(self):
        try:
            from twisted.protocols import _c_urlarg
        except ImportError:
            raise unittest.SkipTest("_c_urlarg module is not available")
        # work exactly like urllib.unquote, including stupid things
        # % followed by a non-hexdigit in the middle and in the end
        self.failUnlessEqual(urllib.unquote("%notreally%n"),
            _c_urlarg.unquote("%notreally%n"))
        # % followed by hexdigit, followed by non-hexdigit
        self.failUnlessEqual(urllib.unquote("%1quite%1"),
            _c_urlarg.unquote("%1quite%1"))
        # unquoted text, followed by some quoted chars, ends in a trailing %
        self.failUnlessEqual(urllib.unquote("blah%21%40%23blah%"),
            _c_urlarg.unquote("blah%21%40%23blah%"))
        # Empty string
        self.failUnlessEqual(urllib.unquote(""), _c_urlarg.unquote(""))

    def testParseqs(self):
        self.failUnlessEqual(cgi.parse_qs("a=b&d=c;+=f"),
            http.parse_qs("a=b&d=c;+=f"))
        self.failUnlessRaises(ValueError, http.parse_qs, "blah",
            strict_parsing = 1)
        self.failUnlessEqual(cgi.parse_qs("a=&b=c", keep_blank_values = 1),
            http.parse_qs("a=&b=c", keep_blank_values = 1))
        self.failUnlessEqual(cgi.parse_qs("a=&b=c"),
            http.parse_qs("a=&b=c"))


    def test_urlparse(self):
        """
        For a given URL, L{http.urlparse} should behave the same as
        L{urlparse}, except it should always return C{str}, never C{unicode}.
        """
        def urls():
            for scheme in ('http', 'https'):
                for host in ('example.com',):
                    for port in (None, 100):
                        for path in ('', 'path'):
                            if port is not None:
                                host = host + ':' + str(port)
                                yield urlunsplit((scheme, host, path, '', ''))


        def assertSameParsing(url, decode):
            """
            Verify that C{url} is parsed into the same objects by both
            L{http.urlparse} and L{urlparse}.
            """
            urlToStandardImplementation = url
            if decode:
                urlToStandardImplementation = url.decode('ascii')
            standardResult = urlparse(urlToStandardImplementation)
            scheme, netloc, path, params, query, fragment = http.urlparse(url)
            self.assertEqual(
                (scheme, netloc, path, params, query, fragment),
                standardResult)
            self.assertTrue(isinstance(scheme, str))
            self.assertTrue(isinstance(netloc, str))
            self.assertTrue(isinstance(path, str))
            self.assertTrue(isinstance(params, str))
            self.assertTrue(isinstance(query, str))
            self.assertTrue(isinstance(fragment, str))

        # With caching, unicode then str
        clear_cache()
        for url in urls():
            assertSameParsing(url, True)
            assertSameParsing(url, False)

        # With caching, str then unicode
        clear_cache()
        for url in urls():
            assertSameParsing(url, False)
            assertSameParsing(url, True)

        # Without caching
        for url in urls():
            clear_cache()
            assertSameParsing(url, True)
            clear_cache()
            assertSameParsing(url, False)


    def test_urlparseRejectsUnicode(self):
        """
        L{http.urlparse} should reject unicode input early.
        """
        self.assertRaises(TypeError, http.urlparse, u'http://example.org/path')


    def testEscchar(self):
        try:
            from twisted.protocols import _c_urlarg
        except ImportError:
            raise unittest.SkipTest("_c_urlarg module is not available")
        self.failUnlessEqual("!@#+b",
            _c_urlarg.unquote("+21+40+23+b", "+"))

class ClientDriver(http.HTTPClient):
    def handleStatus(self, version, status, message):
        self.version = version
        self.status = status
        self.message = message

class ClientStatusParsing(unittest.TestCase):
    def testBaseline(self):
        c = ClientDriver()
        c.lineReceived('HTTP/1.0 201 foo')
        self.failUnlessEqual(c.version, 'HTTP/1.0')
        self.failUnlessEqual(c.status, '201')
        self.failUnlessEqual(c.message, 'foo')

    def testNoMessage(self):
        c = ClientDriver()
        c.lineReceived('HTTP/1.0 201')
        self.failUnlessEqual(c.version, 'HTTP/1.0')
        self.failUnlessEqual(c.status, '201')
        self.failUnlessEqual(c.message, '')

    def testNoMessage_trailingSpace(self):
        c = ClientDriver()
        c.lineReceived('HTTP/1.0 201 ')
        self.failUnlessEqual(c.version, 'HTTP/1.0')
        self.failUnlessEqual(c.status, '201')
        self.failUnlessEqual(c.message, '')

