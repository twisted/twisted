# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test HTTP support.
"""

from zope.interface import implements

from urlparse import urlparse, urlunsplit, clear_cache
import string, random, urllib, cgi

from twisted.python.compat import set
from twisted.python.log import addObserver, removeObserver
from twisted.trial.unittest import TestCase, SkipTest
from twisted.web import http
from twisted.web.http_headers import Headers
from twisted.web.iweb import IHTTPRequestReceiver, IHTTPResponse, IHTTPRequest
from twisted.protocols import loopback
from twisted.internet import protocol
from twisted.internet.protocol import FileWrapper
from twisted.internet.defer import succeed
from twisted.test.test_protocols import StringIOWithoutClosing

from twisted.test.proto_helpers import StringTransport
from twisted.web.test.test_web import DummyChannel

class DateTimeTest(TestCase):
    """Test date parsing functions."""

    def testRoundtrip(self):
        for i in range(10000):
            time = random.randint(0, 2000000000)
            timestr = http.datetimeToString(time)
            time2 = http.stringToDatetime(timestr)
            self.assertEquals(time, time2)


class DummyHTTPHandler(http.Request):

    def process(self):
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



class ResponseTestMixin(object):
    """
    A mixin that provides a simple means of comparing an actual response string
    to an expected response string by performing the minimal parsing.
    """
    def assertResponseEquals(self, responses, expected):
        """
        Assert that the C{responses} matches the C{expected} responses.

        @type responses: C{str}
        @param responses: The bytes sent in response to one or more requests.

        @type expected: C{list} of C{tuple} of C{str}
        @param expected: The expected values for the responses.  Each tuple
            element of the list represents one response.  Each string element
            of the tuple is a full header line without delimiter, except for
            the last element which gives the full response body.
        """
        for response in expected:
            expectedHeaders, expectedContent = response[:-1], response[-1]
            headers, rest = responses.split('\r\n\r\n', 1)
            headers = headers.splitlines()
            self.assertEqual(set(headers), set(expectedHeaders))
            content = rest[:len(expectedContent)]
            responses = rest[len(expectedContent):]
            self.assertEqual(content, expectedContent)



class HTTP1_0TestCase(TestCase, ResponseTestMixin):
    requests = (
        "GET / HTTP/1.0\r\n"
        "\r\n"
        "GET / HTTP/1.1\r\n"
        "Accept: text/html\r\n"
        "\r\n")

    expected_response = [
        ("HTTP/1.0 200 OK",
         "Request: /",
         "Command: GET",
         "Version: HTTP/1.0",
         "Content-Length: 13",
         "'''\nNone\n'''\n")]

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
        self.assertResponseEquals(value, self.expected_response)


class HTTP1_1TestCase(HTTP1_0TestCase):

    requests = (
        "GET / HTTP/1.1\r\n"
        "Accept: text/html\r\n"
        "\r\n"
        "POST / HTTP/1.1\r\n"
        "Content-Length: 10\r\n"
        "\r\n"
        "0123456789POST / HTTP/1.1\r\n"
        "Content-Length: 10\r\n"
        "\r\n"
        "0123456789HEAD / HTTP/1.1\r\n"
        "\r\n")

    expected_response = [
        ("HTTP/1.1 200 OK",
         "Request: /",
         "Command: GET",
         "Version: HTTP/1.1",
         "Content-Length: 13",
         "'''\nNone\n'''\n"),
        ("HTTP/1.1 200 OK",
         "Request: /",
         "Command: POST",
         "Version: HTTP/1.1",
         "Content-Length: 21",
         "'''\n10\n0123456789'''\n"),
        ("HTTP/1.1 200 OK",
         "Request: /",
         "Command: POST",
         "Version: HTTP/1.1",
         "Content-Length: 21",
         "'''\n10\n0123456789'''\n"),
        ("HTTP/1.1 200 OK",
         "Request: /",
         "Command: HEAD",
         "Version: HTTP/1.1",
         "Content-Length: 13",
         "")]



class HTTP1_1_close_TestCase(HTTP1_0TestCase):

    requests = (
        "GET / HTTP/1.1\r\n"
        "Accept: text/html\r\n"
        "Connection: close\r\n"
        "\r\n"
        "GET / HTTP/1.0\r\n"
        "\r\n")

    expected_response = [
        ("HTTP/1.1 200 OK",
         "Connection: close",
         "Request: /",
         "Command: GET",
         "Version: HTTP/1.1",
         "Content-Length: 13",
         "'''\nNone\n'''\n")]



class HTTP0_9TestCase(HTTP1_0TestCase):

    requests = (
        "GET /\r\n")

    expected_response = "HTTP/1.1 400 Bad Request\r\n\r\n"


    def assertResponseEquals(self, response, expectedResponse):
        self.assertEquals(response, expectedResponse)


class HTTPLoopbackTestCase(TestCase):

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



def _prequest(**headers):
    """
    Make a request with the given request headers for the persistence tests.
    """
    request = http.Request(DummyChannel(), None)
    for k, v in headers.iteritems():
        request.requestHeaders.setRawHeaders(k, v)
    return request


class PersistenceTestCase(TestCase):
    """
    Tests for persistent HTTP connections.
    """

    ptests = [#(PRequest(connection="Keep-Alive"), "HTTP/1.0", 1, {'connection' : 'Keep-Alive'}),
              (_prequest(), "HTTP/1.0", 0, {'connection': None}),
              (_prequest(connection=["close"]), "HTTP/1.1", 0, {'connection' : ['close']}),
              (_prequest(), "HTTP/1.1", 1, {'connection': None}),
              (_prequest(), "HTTP/0.9", 0, {'connection': None}),
              ]


    def testAlgorithm(self):
        c = http.HTTPChannel()
        for req, version, correctResult, resultHeaders in self.ptests:
            result = c.checkPersistence(req, version)
            self.assertEquals(result, correctResult)
            for header in resultHeaders.keys():
                self.assertEquals(req.responseHeaders.getRawHeaders(header, None), resultHeaders[header])


class ChunkingTestCase(TestCase):

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



class ParsingTestCase(TestCase):
    """
    Tests for protocol parsing in L{HTTPChannel}.
    """
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
        return a


    def test_basicAuth(self):
        """
        L{HTTPChannel} provides username and password information supplied in
        an I{Authorization} header to the L{Request} which makes it available
        via its C{getUser} and C{getPassword} methods.
        """
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


    def test_headers(self):
        """
        Headers received by L{HTTPChannel} in a request are made available to
        the L{Request}.
        """
        processed = []
        class MyRequest(http.Request):
            def process(self):
                processed.append(self)
                self.finish()

        requestLines = [
            "GET / HTTP/1.0",
            "Foo: bar",
            "baz: Quux",
            "baz: quux",
            "",
            ""]

        channel = self.runRequest('\n'.join(requestLines), MyRequest, 0)
        [request] = processed
        self.assertEquals(
            request.requestHeaders.getRawHeaders('foo'), ['bar'])
        self.assertEquals(
            request.requestHeaders.getRawHeaders('bAz'), ['Quux', 'quux'])


    def test_tooManyHeaders(self):
        """
        L{HTTPChannel} enforces a limit of C{HTTPChannel.maxHeaders} on the
        number of headers received per request.
        """
        processed = []
        class MyRequest(http.Request):
            def process(self):
                processed.append(self)

        requestLines = ["GET / HTTP/1.0"]
        for i in range(http.HTTPChannel.maxHeaders + 2):
            requestLines.append("%s: foo" % (i,))
        requestLines.extend(["", ""])

        channel = self.runRequest("\n".join(requestLines), MyRequest, 0)
        self.assertEqual(processed, [])
        self.assertEqual(
            channel.transport.file.getvalue(),
            "HTTP/1.1 400 Bad Request\r\n\r\n")


    def test_headerLimitPerRequest(self):
        """
        L{HTTPChannel} enforces the limit of C{HTTPChannel.maxHeaders} per
        request so that headers received in an earlier request do not count
        towards the limit when processing a later request.
        """
        processed = []
        class MyRequest(http.Request):
            def process(self):
                processed.append(self)
                self.finish()

        self.patch(http.HTTPChannel, 'maxHeaders', 1)
        requestLines = [
            "GET / HTTP/1.1",
            "Foo: bar",
            "",
            "",
            "GET / HTTP/1.1",
            "Bar: baz",
            "",
            ""]

        channel = self.runRequest("\n".join(requestLines), MyRequest, 0)
        [first, second] = processed
        self.assertEqual(first.getHeader('foo'), 'bar')
        self.assertEqual(second.getHeader('bar'), 'baz')
        self.assertEqual(
            channel.transport.file.getvalue(),
            'HTTP/1.1 200 OK\r\n'
            'Transfer-Encoding: chunked\r\n'
            '\r\n'
            '0\r\n'
            '\r\n'
            'HTTP/1.1 200 OK\r\n'
            'Transfer-Encoding: chunked\r\n'
            '\r\n'
            '0\r\n'
            '\r\n')


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

class QueryArgumentsTestCase(TestCase):
    def testUnquote(self):
        try:
            from twisted.protocols import _c_urlarg
        except ImportError:
            raise SkipTest("_c_urlarg module is not available")
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
            raise SkipTest("_c_urlarg module is not available")
        self.failUnlessEqual("!@#+b",
            _c_urlarg.unquote("+21+40+23+b", "+"))

class ClientDriver(http.HTTPClient):
    def handleStatus(self, version, status, message):
        self.version = version
        self.status = status
        self.message = message

class ClientStatusParsing(TestCase):
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



class RequestTests(TestCase, ResponseTestMixin):
    """
    Tests for L{http.Request}
    """
    def test_argumentlessRequest(self):
        """
        A L{Request} can be instantiated with no arguments.
        """
        request = http.Request()
        self.assertEquals(request.channel, None)
        self.assertEquals(request.transport, None)


    def _compatHeadersTest(self, oldName, newName):
        """
        Verify that each of two different attributes which are associated with
        the same state properly reflect changes made through the other.

        This is used to test that the C{headers}/C{responseHeaders} and
        C{received_headers}/C{requestHeaders} pairs interact properly.
        """
        req = http.Request(DummyChannel(), None)
        getattr(req, newName).setRawHeaders("test", ["lemur"])
        self.assertEqual(getattr(req, oldName)["test"], "lemur")
        setattr(req, oldName, {"foo": "bar"})
        self.assertEqual(
            list(getattr(req, newName).getAllRawHeaders()),
            [("Foo", ["bar"])])
        setattr(req, newName, Headers())
        self.assertEqual(getattr(req, oldName), {})


    def test_received_headers(self):
        """
        L{Request.received_headers} is a backwards compatible API which
        accesses and allows mutation of the state at L{Request.requestHeaders}.
        """
        self._compatHeadersTest('received_headers', 'requestHeaders')


    def test_headers(self):
        """
        L{Request.headers} is a backwards compatible API which accesses and
        allows mutation of the state at L{Request.responseHeaders}.
        """
        self._compatHeadersTest('headers', 'responseHeaders')


    def test_getHeader(self):
        """
        L{http.Request.getHeader} returns the value of the named request
        header.
        """
        req = http.Request(DummyChannel(), None)
        req.requestHeaders.setRawHeaders("test", ["lemur"])
        self.assertEquals(req.getHeader("test"), "lemur")


    def test_getHeaderReceivedMultiples(self):
        """
        When there are multiple values for a single request header,
        L{http.Request.getHeader} returns the last value.
        """
        req = http.Request(DummyChannel(), None)
        req.requestHeaders.setRawHeaders("test", ["lemur", "panda"])
        self.assertEquals(req.getHeader("test"), "panda")


    def test_getHeaderNotFound(self):
        """
        L{http.Request.getHeader} returns C{None} when asked for the value of a
        request header which is not present.
        """
        req = http.Request(DummyChannel(), None)
        self.assertEquals(req.getHeader("test"), None)


    def test_getAllHeaders(self):
        """
        L{http.Request.getAllheaders} returns a C{dict} mapping all request
        header names to their corresponding values.
        """
        req = http.Request(DummyChannel(), None)
        req.requestHeaders.setRawHeaders("test", ["lemur"])
        self.assertEquals(req.getAllHeaders(), {"test": "lemur"})


    def test_getAllHeadersNoHeaders(self):
        """
        L{http.Request.getAllHeaders} returns an empty C{dict} if there are no
        request headers.
        """
        req = http.Request(DummyChannel(), None)
        self.assertEquals(req.getAllHeaders(), {})


    def test_getAllHeadersMultipleHeaders(self):
        """
        When there are multiple values for a single request header,
        L{http.Request.getAllHeaders} returns only the last value.
        """
        req = http.Request(DummyChannel(), None)
        req.requestHeaders.setRawHeaders("test", ["lemur", "panda"])
        self.assertEquals(req.getAllHeaders(), {"test": "panda"})


    def test_setResponseCode(self):
        """
        L{http.Request.setResponseCode} takes a status code and causes it to be
        used as the response status.
        """
        channel = DummyChannel()
        req = http.Request(channel, None)
        req.setResponseCode(201)
        req.write('')
        self.assertEqual(
            channel.transport.written.getvalue().splitlines()[0],
            '%s 201 Created' % (req.clientproto,))


    def test_setResponseCodeAndMessage(self):
        """
        L{http.Request.setResponseCode} takes a status code and a message and
        causes them to be used as the response status.
        """
        channel = DummyChannel()
        req = http.Request(channel, None)
        req.setResponseCode(202, "happily accepted")
        req.write('')
        self.assertEqual(
            channel.transport.written.getvalue().splitlines()[0],
            '%s 202 happily accepted' % (req.clientproto,))


    def test_setResponseCodeAcceptsIntegers(self):
        """
        L{http.Request.setResponseCode} accepts C{int} or C{long} for the code
        parameter and raises L{TypeError} if passed anything else.
        """
        req = http.Request(DummyChannel(), None)
        req.setResponseCode(1)
        req.setResponseCode(1L)
        self.assertRaises(TypeError, req.setResponseCode, "1")


    def test_setHost(self):
        """
        L{http.Request.setHost} sets the value of the host request header.
        """
        req = http.Request(DummyChannel(), None)
        req.setHost("example.com", 443)
        self.assertEqual(
            req.requestHeaders.getRawHeaders("host"), ["example.com"])


    def test_setHeader(self):
        """
        L{http.Request.setHeader} sets the value of the given response header.
        """
        req = http.Request(DummyChannel(), None)
        req.setHeader("test", "lemur")
        self.assertEquals(req.responseHeaders.getRawHeaders("test"), ["lemur"])


    def test_firstWrite(self):
        """
        For an HTTP 1.0 request, L{http.Request.write} sends an HTTP 1.0
        Response-Line and whatever response headers are set.
        """
        req = http.Request(DummyChannel(), None)
        trans = StringTransport()

        req.transport = trans

        req.setResponseCode(200)
        req.clientproto = "HTTP/1.0"
        req.responseHeaders.setRawHeaders("test", ["lemur"])
        req.write('Hello')

        self.assertResponseEquals(
            trans.value(),
            [("HTTP/1.0 200 OK",
              "Test: lemur",
              "Hello")])


    def test_firstWriteHTTP11Chunked(self):
        """
        For an HTTP 1.1 request, L{http.Request.write} sends an HTTP 1.1
        Response-Line, whatever response headers are set, and uses chunked
        encoding for the response body.
        """
        req = http.Request(DummyChannel(), None)
        trans = StringTransport()

        req.transport = trans

        req.setResponseCode(200)
        req.clientproto = "HTTP/1.1"
        req.responseHeaders.setRawHeaders("test", ["lemur"])
        req.write('Hello')
        req.write('World!')

        self.assertResponseEquals(
            trans.value(),
            [("HTTP/1.1 200 OK",
              "Test: lemur",
              "Transfer-Encoding: chunked",
              "5\r\nHello\r\n6\r\nWorld!\r\n")])


    def test_firstWriteLastModified(self):
        """
        For an HTTP 1.0 request for a resource with a known last modified time,
        L{http.Request.write} sends an HTTP Response-Line, whatever response
        headers are set, and a last-modified header with that time.
        """
        req = http.Request(DummyChannel(), None)
        trans = StringTransport()

        req.transport = trans

        req.setResponseCode(200)
        req.clientproto = "HTTP/1.0"
        req.lastModified = 0
        req.responseHeaders.setRawHeaders("test", ["lemur"])
        req.write('Hello')

        self.assertResponseEquals(
            trans.value(),
            [("HTTP/1.0 200 OK",
              "Test: lemur",
              "Last-Modified: Thu, 01 Jan 1970 00:00:00 GMT",
              "Hello")])


    def test_parseCookies(self):
        """
        L{http.Request.parseCookies} extracts cookies from C{requestHeaders}
        and adds them to C{received_cookies}.
        """
        req = http.Request(DummyChannel(), None)
        req.requestHeaders.setRawHeaders(
            "cookie", ['test="lemur"; test2="panda"'])
        req.parseCookies()
        self.assertEquals(req.received_cookies, {"test": '"lemur"',
                                                 "test2": '"panda"'})


    def test_parseCookiesMultipleHeaders(self):
        """
        L{http.Request.parseCookies} can extract cookies from multiple Cookie
        headers.
        """
        req = http.Request(DummyChannel(), None)
        req.requestHeaders.setRawHeaders(
            "cookie", ['test="lemur"', 'test2="panda"'])
        req.parseCookies()
        self.assertEquals(req.received_cookies, {"test": '"lemur"',
                                                 "test2": '"panda"'})




class StubRequestReceiver(object):
    """
    A stub request receiver that simply records requests received.

    @ivar requests: List of requests.
    @ivar responseToReturn: The response to return from L{requestReceived}.
    """
    implements(IHTTPRequestReceiver)

    responseToReturn = None

    def __init__(self):
        self.requests = []
        self.responses = []


    def requestReceived(self, request):
        """
        Record the request in C{self.requests}

        @return: L{responseToReturn}
        """
        self.requests.append(request)
        return succeed(self.responseToReturn)



class StringResponse(object):
    """
    A simple L{IHTTPResponse} implementation that writes a string of data as
    the body.
    """
    implements(IHTTPResponse)

    def __init__(self, code, headers, data):
        """
        @param code: The HTTP code to use.
        @type code: C{int}

        @param headers: A dict of response headers.
        @type headers: C{dict}

        @param data: The body data.
        @type data: C{str}
        """
        self.code = code
        self.headers = headers
        self.data = data


    def getResponseCode(self):
        """
        Return the previously specified code and the string C{"Whatever"} as
        the message.
        """
        return (self.code, "Whatever")


    def getHeaders(self):
        """
        Return the previously specified headers.
        """
        return self.headers


    def writeBody(self, consumer):
        """
        Write the previously specified data to the consumer.
        """
        self.responseReceiver = consumer
        consumer.write(self.data)
        consumer.finishResponse()



class ChannelTests(TestCase):

    def setUp(self):
        self.io = StringIOWithoutClosing()
        self.transport = FileWrapper(self.io)
        self.channel = http.HTTPChannel()
        self.channel.makeConnection(self.transport)


    def test_callRequestReceivedOnRequestReceiver(self):
        """
        If L{HTTPChannel.setRequestReceiver} is used, the passed object will be
        notified of requests.
        """
        receiver = StubRequestReceiver()
        receiver.responseToReturn = StringResponse(200, {}, "")

        self.channel.setRequestReceiver(receiver)
        self.channel.dataReceived('GET / HTTP/1.1\r\n\r\n')

        self.assertEquals(len(receiver.requests), 1)
        request = receiver.requests[0]

        self.assertEquals(request.path, '/')
        self.assertEquals(request.method, 'GET')
        self.assertEquals(request.uri, '/')
        self.assertEquals(request.clientproto, "HTTP/1.1")


    def request(self, response, request_data=None):
        if request_data is None:
            request_data = "GET / HTTP/1.1\r\n\r\n"
        receiver = StubRequestReceiver()
        receiver.responseToReturn = response

        self.channel.setRequestReceiver(receiver)
        self.channel.dataReceived(request_data)
        self.assertEquals(len(receiver.requests), 1)
        return receiver.requests[0]

    def assertResponse(self, response, expected_response, request_data=None):
        self.request(response, request_data=request_data)
        expected_response = expected_response.replace('\n', '\r\n')
        self.assertEquals(self.io.getvalue(), expected_response)
        self.io.seek(0,0)
        self.io.truncate()


    def test_processResponseFromRequestReceiver(self):
        """
        When the channel notifies the request receiver of the request, it will
        handle a response object returned from that request by fetching various
        data from it, writing it to the transport, and telling it to write its
        to the channel.
        """
        expected_response = """\
HTTP/1.1 200 Whatever
Content-length: 7

Thanks!"""
        self.assertResponse(
            StringResponse(200, {"content-length": "7"}, "Thanks!"),
            expected_response)


    def test_chunkedResponses(self):
        """
        When the response doesn't specify a content-length in the headers,
        chunked encoding will be used.
        """
        expected_response ="""\
HTTP/1.1 200 Whatever
Transfer-encoding: chunked

7
Thanks!
0

"""
        self.assertResponse(StringResponse(200, {}, "Thanks!"),
                            expected_response)


    def test_onlyChunkWithHTTP1_1(self):
        """
        Chunked encoding will not be used with HTTP 1.0.
        """
        expected_response = """\
HTTP/1.0 200 Whatever

Thanks!"""
        self.assertResponse(StringResponse(200, {}, "Thanks!"),
                            expected_response,
                            request_data="GET / HTTP/1.0\r\n\r\n")


    def test_head(self):
        """
        HEAD requests should not have a body written. They should also not have
        a transfer-encoding of chunked, even when content-length is not
        specified.
        """
        expected_response = """\
HTTP/1.1 200 Whatever
Foo: bar

"""
        self.assertResponse(StringResponse(200, {"foo": "bar"}, "Thanks!"),
                            expected_response,
                            request_data="HEAD / HTTP/1.1\r\n\r\n")


    def test_noBodyCodes(self):
        """
        If one of the codes that the response has returned is in the set of
        codes that no body should be written for, no body should be written.
        """
        for code in http.NO_BODY_CODES:
            expected_response = """\
HTTP/1.1 %d Whatever
Foo: bar

""" % (code,)

            self.assertResponse(StringResponse(code, {"foo": "bar"}, "Thanks!"),
                                expected_response)


    def test_unregisterProducer(self):
        """
        L{unregisterProducer} should be delegated to the underlying transport.
        """
        response = StringResponse(200, {}, "Hi!")
        self.request(response)
        unregistrations = []
        def unregisterProducer():
            unregistrations.append(True)
        self.transport.unregisterProducer = unregisterProducer

        producer = object()
        streaming = object()
        response.responseReceiver.unregisterProducer()
        self.assertEquals(unregistrations, [True])


    def test_registerProducer(self):
        """
        L{registerProducer} should be delegated to the underlying transport.
        """
        response = StringResponse(200, {}, "Hi!")
        self.request(response)
        registrations = []
        def registerProducer(producer, streaming):
            registrations.append((producer, streaming))
        self.transport.registerProducer = registerProducer

        producer = object()
        streaming = object()
        response.responseReceiver.registerProducer(producer, streaming)
        self.assertEquals(registrations, [(producer, streaming)])


    def test_twoRequests(self):

        chunked_response = StringResponse(200, {}, "Hi")
        length_response = StringResponse(200, {"content-length": 2}, "Hi")

        self.request(chunked_response)
        self.request(length_response)

        self.assertEquals(self.io.getvalue(),
                          """\
HTTP/1.1 200 Whatever
Transfer-encoding: chunked

2
Hi
0

HTTP/1.1 200 Whatever
Content-length: 2

Hi""".replace('\n', '\r\n'))

    def test_finishResponseWithNoBody(self):
        """
        When finishing a response without having written any body, a complete
        response should still be sent.
        """
        response = StringResponse(200, {}, "Hi")
        response.writeBody = lambda channel: channel.finishResponse()
        self.request(response)
        self.assertEquals(self.io.getvalue(),
                          """\
HTTP/1.1 200 Whatever
Transfer-encoding: chunked

0

""".replace("\n", "\r\n"))


    def test_logging(self):
        """
        When finishing a response, the request should be logged.
        """
        response = StringResponse(200, {}, "Hi")
        logs = []
        addObserver(logs.append)
        try:
            request = self.request(response)
        finally:
            removeObserver(logs.append)

        self.assertEquals(len(logs), 1)
        log = logs[0]

        self.assertEquals(log["interface"], IHTTPRequest)
        self.assertIdentical(log["request"], request)
        self.assertEquals(log["client"], self.transport.getPeer())
        self.assertEquals(log["sentLength"], 2)




# XXX Test cleanup between requests (_chunked!). Or maybe the thing passed to
# writeBody really ought to be separate from the channel. :\ Fortunately that
# change would not actually change any APIs.

# XXX Test that logged requests have the correct sent data size.

# XXX move the crap in Request.requestReceived somewhere else...

# XXX Test HTTPResponse (or just Response).

# XXX Maybe make Request take all of its data in __init__.

# It should take a request in its constructor. As much as that seems really
# weird, I think it's actually exactly the right direction of dependency. It
# allows the response to calculate things based on the request. It should have
# setLastModified and setETag, for example.

# It should also have setHeader, addCookie, etc.

# It should have redirect.
