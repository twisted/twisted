# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the old L{twisted.web.client} APIs, C{getPage} and friends.
"""

from __future__ import division, absolute_import

import os
from errno import ENOSPC

try:
    from urlparse import urlparse, urljoin
except ImportError:
    from urllib.parse import urlparse, urljoin

from twisted.python.compat import _PY3, networkString, nativeString, intToBytes
from twisted.trial import unittest
from twisted.web import server, client, error, resource
from twisted.internet import reactor, defer, interfaces
from twisted.python.filepath import FilePath
from twisted.python.log import msg
from twisted.protocols.policies import WrappingFactory
from twisted.test.proto_helpers import StringTransport

try:
    from twisted.internet import ssl
except:
    ssl = None

from twisted import test
serverPEM = FilePath(test.__file__.encode("utf-8")).sibling(b'server.pem')
serverPEMPath = nativeString(serverPEM.path)

# Remove this in #6177, when static is ported to Python 3:
if _PY3:
    from twisted.web.test.test_web import Data
else:
    from twisted.web.static import Data

# Remove this in #6178, when util is ported to Python 3:
if _PY3:
    class Redirect(resource.Resource):
        isLeaf = 1

        def __init__(self, url):
            resource.Resource.__init__(self)
            self.url = url

        def render(self, request):
            request.redirect(self.url)
            return b""

        def getChild(self, name, request):
            return self
else:
    from twisted.web.util import Redirect

_PY3DownloadSkip = "downloadPage will be ported to Python 3 in ticket #6197."


class ExtendedRedirect(resource.Resource):
    """
    Redirection resource.

    The HTTP status code is set according to the C{code} query parameter.

    @type lastMethod: C{str}
    @ivar lastMethod: Last handled HTTP request method
    """
    isLeaf = 1
    lastMethod = None


    def __init__(self, url):
        resource.Resource.__init__(self)
        self.url = url


    def render(self, request):
        if self.lastMethod:
            self.lastMethod = request.method
            return b"OK Thnx!"
        else:
            self.lastMethod = request.method
            code = int(request.args[b'code'][0])
            return self.redirectTo(self.url, request, code)


    def getChild(self, name, request):
        return self


    def redirectTo(self, url, request, code):
        request.setResponseCode(code)
        request.setHeader(b"location", url)
        return b"OK Bye!"



class ForeverTakingResource(resource.Resource):
    """
    L{ForeverTakingResource} is a resource which never finishes responding
    to requests.
    """
    def __init__(self, write=False):
        resource.Resource.__init__(self)
        self._write = write

    def render(self, request):
        if self._write:
            request.write(b'some bytes')
        return server.NOT_DONE_YET


class CookieMirrorResource(resource.Resource):
    def render(self, request):
        l = []
        for k,v in sorted(list(request.received_cookies.items())):
            l.append((nativeString(k), nativeString(v)))
        l.sort()
        return networkString(repr(l))

class RawCookieMirrorResource(resource.Resource):
    def render(self, request):
        header = request.getHeader(b'cookie')
        if header is None:
            return b'None'
        return networkString(repr(nativeString(header)))

class ErrorResource(resource.Resource):

    def render(self, request):
        request.setResponseCode(401)
        if request.args.get(b"showlength"):
            request.setHeader(b"content-length", b"0")
        return b""

class NoLengthResource(resource.Resource):

    def render(self, request):
        return b"nolength"



class HostHeaderResource(resource.Resource):
    """
    A testing resource which renders itself as the value of the host header
    from the request.
    """
    def render(self, request):
        return request.received_headers[b'host']



class PayloadResource(resource.Resource):
    """
    A testing resource which renders itself as the contents of the request body
    as long as the request body is 100 bytes long, otherwise which renders
    itself as C{"ERROR"}.
    """
    def render(self, request):
        data = request.content.read()
        contentLength = request.received_headers[b'content-length']
        if len(data) != 100 or int(contentLength) != 100:
            return b"ERROR"
        return data


class DelayResource(resource.Resource):

    def __init__(self, seconds):
        self.seconds = seconds

    def render(self, request):
        def response():
            request.write(b'some bytes')
            request.finish()
        reactor.callLater(self.seconds, response)
        return server.NOT_DONE_YET


class BrokenDownloadResource(resource.Resource):

    def render(self, request):
        # only sends 3 bytes even though it claims to send 5
        request.setHeader(b"content-length", b"5")
        request.write(b'abc')
        return b''

class CountingRedirect(Redirect):
    """
    A L{Redirect} resource that keeps track of the number of times the
    resource has been accessed.
    """
    def __init__(self, *a, **kw):
        Redirect.__init__(self, *a, **kw)
        self.count = 0

    def render(self, request):
        self.count += 1
        return Redirect.render(self, request)


class CountingResource(resource.Resource):
    """
    A resource that keeps track of the number of times it has been accessed.
    """
    def __init__(self):
        resource.Resource.__init__(self)
        self.count = 0

    def render(self, request):
        self.count += 1
        return b"Success"


class ParseUrlTestCase(unittest.TestCase):
    """
    Test URL parsing facility and defaults values.
    """

    def test_parse(self):
        """
        L{client._parse} correctly parses a URL into its various components.
        """
        # The default port for HTTP is 80.
        self.assertEqual(
            client._parse(b'http://127.0.0.1/'),
            (b'http', b'127.0.0.1', 80, b'/'))

        # The default port for HTTPS is 443.
        self.assertEqual(
            client._parse(b'https://127.0.0.1/'),
            (b'https', b'127.0.0.1', 443, b'/'))

        # Specifying a port.
        self.assertEqual(
            client._parse(b'http://spam:12345/'),
            (b'http', b'spam', 12345, b'/'))

        # Weird (but commonly accepted) structure uses default port.
        self.assertEqual(
            client._parse(b'http://spam:/'),
            (b'http', b'spam', 80, b'/'))

        # Spaces in the hostname are trimmed, the default path is /.
        self.assertEqual(
            client._parse(b'http://foo '),
            (b'http', b'foo', 80, b'/'))


    def test_externalUnicodeInterference(self):
        """
        L{client._parse} should return C{bytes} for the scheme, host, and path
        elements of its return tuple, even when passed an URL which has
        previously been passed to L{urlparse} as a C{unicode} string.
        """
        badInput = u'http://example.com/path'
        goodInput = badInput.encode('ascii')
        urlparse(badInput)
        scheme, host, port, path = client._parse(goodInput)
        self.assertIsInstance(scheme, bytes)
        self.assertIsInstance(host, bytes)
        self.assertIsInstance(path, bytes)



class HTTPPageGetterTests(unittest.TestCase):
    """
    Tests for L{HTTPPagerGetter}, the HTTP client protocol implementation
    used to implement L{getPage}.
    """
    def test_earlyHeaders(self):
        """
        When a connection is made, L{HTTPPagerGetter} sends the headers from
        its factory's C{headers} dict.  If I{Host} or I{Content-Length} is
        present in this dict, the values are not sent, since they are sent with
        special values before the C{headers} dict is processed.  If
        I{User-Agent} is present in the dict, it overrides the value of the
        C{agent} attribute of the factory.  If I{Cookie} is present in the
        dict, its value is added to the values from the factory's C{cookies}
        attribute.
        """
        factory = client.HTTPClientFactory(
            b'http://foo/bar',
            agent=b"foobar",
            cookies={b'baz': b'quux'},
            postdata=b"some data",
            headers={
                b'Host': b'example.net',
                b'User-Agent': b'fooble',
                b'Cookie': b'blah blah',
                b'Content-Length': b'12981',
                b'Useful': b'value'})
        transport = StringTransport()
        protocol = client.HTTPPageGetter()
        protocol.factory = factory
        protocol.makeConnection(transport)
        result = transport.value()
        for expectedHeader in [
            b"Host: example.net\r\n",
            b"User-Agent: foobar\r\n",
            b"Content-Length: 9\r\n",
            b"Useful: value\r\n",
            b"connection: close\r\n",
            b"Cookie: blah blah; baz=quux\r\n"]:
            self.assertIn(expectedHeader, result)



class WebClientTestCase(unittest.TestCase):
    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")

    def setUp(self):
        self.agent = None # for twisted.web.client.Agent test
        self.cleanupServerConnections = 0
        r = resource.Resource()
        r.putChild(b"file", Data(b"0123456789", b"text/html"))
        r.putChild(b"redirect", Redirect(b"/file"))
        self.infiniteRedirectResource = CountingRedirect(b"/infiniteRedirect")
        r.putChild(b"infiniteRedirect", self.infiniteRedirectResource)
        r.putChild(b"wait", ForeverTakingResource())
        r.putChild(b"write-then-wait", ForeverTakingResource(write=True))
        r.putChild(b"error", ErrorResource())
        r.putChild(b"nolength", NoLengthResource())
        r.putChild(b"host", HostHeaderResource())
        r.putChild(b"payload", PayloadResource())
        r.putChild(b"broken", BrokenDownloadResource())
        r.putChild(b"cookiemirror", CookieMirrorResource())
        r.putChild(b'delay1', DelayResource(1))
        r.putChild(b'delay2', DelayResource(2))

        self.afterFoundGetCounter = CountingResource()
        r.putChild(b"afterFoundGetCounter", self.afterFoundGetCounter)
        r.putChild(b"afterFoundGetRedirect", Redirect(b"/afterFoundGetCounter"))

        miscasedHead = Data(b"miscased-head GET response content", b"major/minor")
        miscasedHead.render_Head = lambda request: b"miscased-head content"
        r.putChild(b"miscased-head", miscasedHead)

        self.extendedRedirect = ExtendedRedirect(b'/extendedRedirect')
        r.putChild(b"extendedRedirect", self.extendedRedirect)
        self.site = server.Site(r, timeout=None)
        self.wrapper = WrappingFactory(self.site)
        self.port = self._listen(self.wrapper)
        self.portno = self.port.getHost().port

    def tearDown(self):
        if self.agent:
            # clean up connections for twisted.web.client.Agent test.
            self.agent.closeCachedConnections()
            self.agent = None

        # If the test indicated it might leave some server-side connections
        # around, clean them up.
        connections = list(self.wrapper.protocols.keys())
        # If there are fewer server-side connections than requested,
        # that's okay.  Some might have noticed that the client closed
        # the connection and cleaned up after themselves.
        for n in range(min(len(connections), self.cleanupServerConnections)):
            proto = connections.pop()
            msg("Closing %r" % (proto,))
            proto.transport.loseConnection()
        if connections:
            msg("Some left-over connections; this test is probably buggy.")
        return self.port.stopListening()

    def getURL(self, path):
        host = "http://127.0.0.1:%d/" % self.portno
        return networkString(urljoin(host, nativeString(path)))

    def testPayload(self):
        s = b"0123456789" * 10
        return client.getPage(self.getURL("payload"), postdata=s
                              ).addCallback(self.assertEqual, s
            )


    def test_getPageBrokenDownload(self):
        """
        If the connection is closed before the number of bytes indicated by
        I{Content-Length} have been received, the L{Deferred} returned by
        L{getPage} fails with L{PartialDownloadError}.
        """
        d = client.getPage(self.getURL("broken"))
        d = self.assertFailure(d, client.PartialDownloadError)
        d.addCallback(lambda exc: self.assertEqual(exc.response, b"abc"))
        return d


    def test_downloadPageBrokenDownload(self):
        """
        If the connection is closed before the number of bytes indicated by
        I{Content-Length} have been received, the L{Deferred} returned by
        L{downloadPage} fails with L{PartialDownloadError}.
        """
        # test what happens when download gets disconnected in the middle
        path = FilePath(self.mktemp())
        d = client.downloadPage(self.getURL("broken"), path.path)
        d = self.assertFailure(d, client.PartialDownloadError)

        def checkResponse(response):
            """
            The HTTP status code from the server is propagated through the
            C{PartialDownloadError}.
            """
            self.assertEqual(response.status, b"200")
            self.assertEqual(response.message, b"OK")
            return response
        d.addCallback(checkResponse)

        def cbFailed(ignored):
            self.assertEqual(path.getContent(), b"abc")
        d.addCallback(cbFailed)
        return d

    def test_downloadPageLogsFileCloseError(self):
        """
        If there is an exception closing the file being written to after the
        connection is prematurely closed, that exception is logged.
        """
        class BrokenFile:
            def write(self, bytes):
                pass

            def close(self):
                raise IOError(ENOSPC, "No file left on device")

        d = client.downloadPage(self.getURL("broken"), BrokenFile())
        d = self.assertFailure(d, client.PartialDownloadError)
        def cbFailed(ignored):
            self.assertEqual(len(self.flushLoggedErrors(IOError)), 1)
        d.addCallback(cbFailed)
        return d


    def testHostHeader(self):
        # if we pass Host header explicitly, it should be used, otherwise
        # it should extract from url
        return defer.gatherResults([
            client.getPage(self.getURL("host")).addCallback(
                    self.assertEqual, b"127.0.0.1:" + intToBytes(self.portno)),
            client.getPage(self.getURL("host"),
                           headers={b"Host": b"www.example.com"}).addCallback(
                    self.assertEqual, b"www.example.com")])


    def test_getPage(self):
        """
        L{client.getPage} returns a L{Deferred} which is called back with
        the body of the response if the default method B{GET} is used.
        """
        d = client.getPage(self.getURL("file"))
        d.addCallback(self.assertEqual, b"0123456789")
        return d


    def test_getPageHEAD(self):
        """
        L{client.getPage} returns a L{Deferred} which is called back with
        the empty string if the method is I{HEAD} and there is a successful
        response code.
        """
        d = client.getPage(self.getURL("file"), method=b"HEAD")
        d.addCallback(self.assertEqual, b"")
        return d


    def test_getPageNotQuiteHEAD(self):
        """
        If the request method is a different casing of I{HEAD} (ie, not all
        capitalized) then it is not a I{HEAD} request and the response body
        is returned.
        """
        d = client.getPage(self.getURL("miscased-head"), method=b'Head')
        d.addCallback(self.assertEqual, b"miscased-head content")
        return d


    def test_timeoutNotTriggering(self):
        """
        When a non-zero timeout is passed to L{getPage} and the page is
        retrieved before the timeout period elapses, the L{Deferred} is
        called back with the contents of the page.
        """
        d = client.getPage(self.getURL("host"), timeout=100)
        d.addCallback(self.assertEqual,
                      networkString("127.0.0.1:%s" % (self.portno,)))
        return d


    def test_timeoutTriggering(self):
        """
        When a non-zero timeout is passed to L{getPage} and that many
        seconds elapse before the server responds to the request. the
        L{Deferred} is errbacked with a L{error.TimeoutError}.
        """
        # This will probably leave some connections around.
        self.cleanupServerConnections = 1
        return self.assertFailure(
            client.getPage(self.getURL("wait"), timeout=0.000001),
            defer.TimeoutError)


    def testDownloadPage(self):
        downloads = []
        downloadData = [(b"file", self.mktemp(), b"0123456789"),
                        (b"nolength", self.mktemp(), b"nolength")]

        for (url, name, data) in downloadData:
            d = client.downloadPage(self.getURL(url), name)
            d.addCallback(self._cbDownloadPageTest, data, name)
            downloads.append(d)
        return defer.gatherResults(downloads)

    def _cbDownloadPageTest(self, ignored, data, name):
        bytes = file(name, "rb").read()
        self.assertEqual(bytes, data)

    def testDownloadPageError1(self):
        class errorfile:
            def write(self, data):
                raise IOError("badness happened during write")
            def close(self):
                pass
        ef = errorfile()
        return self.assertFailure(
            client.downloadPage(self.getURL("file"), ef),
            IOError)

    def testDownloadPageError2(self):
        class errorfile:
            def write(self, data):
                pass
            def close(self):
                raise IOError("badness happened during close")
        ef = errorfile()
        return self.assertFailure(
            client.downloadPage(self.getURL("file"), ef),
            IOError)

    def testDownloadPageError3(self):
        # make sure failures in open() are caught too. This is tricky.
        # Might only work on posix.
        tmpfile = open("unwritable", "wb")
        tmpfile.close()
        os.chmod("unwritable", 0) # make it unwritable (to us)
        d = self.assertFailure(
            client.downloadPage(self.getURL("file"), "unwritable"),
            IOError)
        d.addBoth(self._cleanupDownloadPageError3)
        return d

    def _cleanupDownloadPageError3(self, ignored):
        os.chmod("unwritable", 0o700)
        os.unlink("unwritable")
        return ignored

    def _downloadTest(self, method):
        dl = []
        for (url, code) in [("nosuchfile", b"404"), ("error", b"401"),
                            ("error?showlength=1", b"401")]:
            d = method(url)
            d = self.assertFailure(d, error.Error)
            d.addCallback(lambda exc, code=code: self.assertEqual(exc.args[0], code))
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

    def testServerError(self):
        return self._downloadTest(lambda url: client.getPage(self.getURL(url)))

    def testDownloadServerError(self):
        return self._downloadTest(lambda url: client.downloadPage(self.getURL(url), url.split('?')[0]))

    def testFactoryInfo(self):
        url = self.getURL('file')
        scheme, host, port, path = client._parse(url)
        factory = client.HTTPClientFactory(url)
        reactor.connectTCP(nativeString(host), port, factory)
        return factory.deferred.addCallback(self._cbFactoryInfo, factory)

    def _cbFactoryInfo(self, ignoredResult, factory):
        self.assertEqual(factory.status, b'200')
        self.assert_(factory.version.startswith(b'HTTP/'))
        self.assertEqual(factory.message, b'OK')
        self.assertEqual(factory.response_headers[b'content-length'][0], b'10')


    def test_followRedirect(self):
        """
        By default, L{client.getPage} follows redirects and returns the content
        of the target resource.
        """
        d = client.getPage(self.getURL("redirect"))
        d.addCallback(self.assertEqual, b"0123456789")
        return d


    def test_noFollowRedirect(self):
        """
        If C{followRedirect} is passed a false value, L{client.getPage} does not
        follow redirects and returns a L{Deferred} which fails with
        L{error.PageRedirect} when it encounters one.
        """
        d = self.assertFailure(
            client.getPage(self.getURL("redirect"), followRedirect=False),
            error.PageRedirect)
        d.addCallback(self._cbCheckLocation)
        return d


    def _cbCheckLocation(self, exc):
        self.assertEqual(exc.location, b"/file")


    def test_infiniteRedirection(self):
        """
        When more than C{redirectLimit} HTTP redirects are encountered, the
        page request fails with L{InfiniteRedirection}.
        """
        def checkRedirectCount(*a):
            self.assertEqual(f._redirectCount, 13)
            self.assertEqual(self.infiniteRedirectResource.count, 13)

        f = client._makeGetterFactory(
            self.getURL('infiniteRedirect'),
            client.HTTPClientFactory,
            redirectLimit=13)
        d = self.assertFailure(f.deferred, error.InfiniteRedirection)
        d.addCallback(checkRedirectCount)
        return d


    def test_isolatedFollowRedirect(self):
        """
        C{client.HTTPPagerGetter} instances each obey the C{followRedirect}
        value passed to the L{client.getPage} call which created them.
        """
        d1 = client.getPage(self.getURL('redirect'), followRedirect=True)
        d2 = client.getPage(self.getURL('redirect'), followRedirect=False)

        d = self.assertFailure(d2, error.PageRedirect
            ).addCallback(lambda dummy: d1)
        return d


    def test_afterFoundGet(self):
        """
        Enabling unsafe redirection behaviour overwrites the method of
        redirected C{POST} requests with C{GET}.
        """
        url = self.getURL('extendedRedirect?code=302')
        f = client.HTTPClientFactory(url, followRedirect=True, method=b"POST")
        self.assertFalse(
            f.afterFoundGet,
            "By default, afterFoundGet must be disabled")

        def gotPage(page):
            self.assertEqual(
                self.extendedRedirect.lastMethod,
                b"GET",
                "With afterFoundGet, the HTTP method must change to GET")

        d = client.getPage(
            url, followRedirect=True, afterFoundGet=True, method=b"POST")
        d.addCallback(gotPage)
        return d


    def test_downloadAfterFoundGet(self):
        """
        Passing C{True} for C{afterFoundGet} to L{client.downloadPage} invokes
        the same kind of redirect handling as passing that argument to
        L{client.getPage} invokes.
        """
        url = self.getURL('extendedRedirect?code=302')

        def gotPage(page):
            self.assertEqual(
                self.extendedRedirect.lastMethod,
                b"GET",
                "With afterFoundGet, the HTTP method must change to GET")

        d = client.downloadPage(url, "downloadTemp",
            followRedirect=True, afterFoundGet=True, method="POST")
        d.addCallback(gotPage)
        return d


    def test_afterFoundGetMakesOneRequest(self):
        """
        When C{afterFoundGet} is C{True}, L{client.getPage} only issues one
        request to the server when following the redirect.  This is a regression
        test, see #4760.
        """
        def checkRedirectCount(*a):
            self.assertEqual(self.afterFoundGetCounter.count, 1)

        url = self.getURL('afterFoundGetRedirect')
        d = client.getPage(
            url, followRedirect=True, afterFoundGet=True, method=b"POST")
        d.addCallback(checkRedirectCount)
        return d


    def testPartial(self):
        name = self.mktemp()
        f = open(name, "wb")
        f.write(b"abcd")
        f.close()

        partialDownload = [(True, b"abcd456789"),
                           (True, b"abcd456789"),
                           (False, b"0123456789")]

        d = defer.succeed(None)
        for (partial, expectedData) in partialDownload:
            d.addCallback(self._cbRunPartial, name, partial)
            d.addCallback(self._cbPartialTest, expectedData, name)

        return d

    testPartial.skip = "Cannot test until webserver can serve partial data properly"

    def _cbRunPartial(self, ignored, name, partial):
        return client.downloadPage(self.getURL("file"), name, supportPartial=partial)

    def _cbPartialTest(self, ignored, expectedData, filename):
        bytes = file(filename, "rb").read()
        self.assertEqual(bytes, expectedData)


    def test_downloadTimeout(self):
        """
        If the timeout indicated by the C{timeout} parameter to
        L{client.HTTPDownloader.__init__} elapses without the complete response
        being received, the L{defer.Deferred} returned by
        L{client.downloadPage} fires with a L{Failure} wrapping a
        L{defer.TimeoutError}.
        """
        self.cleanupServerConnections = 2
        # Verify the behavior if no bytes are ever written.
        first = client.downloadPage(
            self.getURL("wait"),
            self.mktemp(), timeout=0.01)

        # Verify the behavior if some bytes are written but then the request
        # never completes.
        second = client.downloadPage(
            self.getURL("write-then-wait"),
            self.mktemp(), timeout=0.01)

        return defer.gatherResults([
            self.assertFailure(first, defer.TimeoutError),
            self.assertFailure(second, defer.TimeoutError)])


    def test_downloadHeaders(self):
        """
        After L{client.HTTPDownloader.deferred} fires, the
        L{client.HTTPDownloader} instance's C{status} and C{response_headers}
        attributes are populated with the values from the response.
        """
        def checkHeaders(factory):
            self.assertEqual(factory.status, b'200')
            self.assertEqual(factory.response_headers[b'content-type'][0], b'text/html')
            self.assertEqual(factory.response_headers[b'content-length'][0], b'10')
            os.unlink(factory.fileName)
        factory = client._makeGetterFactory(
            self.getURL('file'),
            client.HTTPDownloader,
            fileOrName=self.mktemp())
        return factory.deferred.addCallback(lambda _: checkHeaders(factory))


    def test_downloadCookies(self):
        """
        The C{cookies} dict passed to the L{client.HTTPDownloader}
        initializer is used to populate the I{Cookie} header included in the
        request sent to the server.
        """
        output = self.mktemp()
        factory = client._makeGetterFactory(
            self.getURL('cookiemirror'),
            client.HTTPDownloader,
            fileOrName=output,
            cookies={b'foo': b'bar'})
        def cbFinished(ignored):
            self.assertEqual(
                FilePath(output).getContent(),
                "[('foo', 'bar')]")
        factory.deferred.addCallback(cbFinished)
        return factory.deferred


    def test_downloadRedirectLimit(self):
        """
        When more than C{redirectLimit} HTTP redirects are encountered, the
        page request fails with L{InfiniteRedirection}.
        """
        def checkRedirectCount(*a):
            self.assertEqual(f._redirectCount, 7)
            self.assertEqual(self.infiniteRedirectResource.count, 7)

        f = client._makeGetterFactory(
            self.getURL('infiniteRedirect'),
            client.HTTPDownloader,
            fileOrName=self.mktemp(),
            redirectLimit=7)
        d = self.assertFailure(f.deferred, error.InfiniteRedirection)
        d.addCallback(checkRedirectCount)
        return d

    if _PY3:
        for method in (
            test_downloadPageBrokenDownload,
            test_downloadPageLogsFileCloseError,
            testDownloadPage,
            testDownloadPageError1,
            testDownloadPageError2,
            testDownloadPageError3,
            testDownloadServerError,
            test_downloadAfterFoundGet,
            testPartial,
            test_downloadTimeout,
            test_downloadHeaders,
            test_downloadCookies,
            test_downloadRedirectLimit):
            method.skip = _PY3DownloadSkip
        del method



class WebClientSSLTestCase(WebClientTestCase):
    def _listen(self, site):
        return reactor.listenSSL(
            0, site,
            contextFactory=ssl.DefaultOpenSSLContextFactory(
                serverPEMPath, serverPEMPath),
            interface="127.0.0.1")

    def getURL(self, path):
        return networkString("https://127.0.0.1:%d/%s" % (self.portno, path))

    def testFactoryInfo(self):
        url = self.getURL('file')
        scheme, host, port, path = client._parse(url)
        factory = client.HTTPClientFactory(url)
        reactor.connectSSL(nativeString(host), port, factory,
                           ssl.ClientContextFactory())
        # The base class defines _cbFactoryInfo correctly for this
        return factory.deferred.addCallback(self._cbFactoryInfo, factory)



class WebClientRedirectBetweenSSLandPlainText(unittest.TestCase):
    def getHTTPS(self, path):
        return networkString("https://127.0.0.1:%d/%s" % (self.tlsPortno, path))

    def getHTTP(self, path):
        return networkString("http://127.0.0.1:%d/%s" % (self.plainPortno, path))

    def setUp(self):
        plainRoot = Data(b'not me', b'text/plain')
        tlsRoot = Data(b'me neither', b'text/plain')

        plainSite = server.Site(plainRoot, timeout=None)
        tlsSite = server.Site(tlsRoot, timeout=None)

        self.tlsPort = reactor.listenSSL(
            0, tlsSite,
            contextFactory=ssl.DefaultOpenSSLContextFactory(
                serverPEMPath, serverPEMPath),
            interface="127.0.0.1")
        self.plainPort = reactor.listenTCP(0, plainSite, interface="127.0.0.1")

        self.plainPortno = self.plainPort.getHost().port
        self.tlsPortno = self.tlsPort.getHost().port

        plainRoot.putChild(b'one', Redirect(self.getHTTPS('two')))
        tlsRoot.putChild(b'two', Redirect(self.getHTTP('three')))
        plainRoot.putChild(b'three', Redirect(self.getHTTPS('four')))
        tlsRoot.putChild(b'four', Data(b'FOUND IT!', b'text/plain'))

    def tearDown(self):
        ds = list(
            map(defer.maybeDeferred,
                [self.plainPort.stopListening, self.tlsPort.stopListening]))
        return defer.gatherResults(ds)

    def testHoppingAround(self):
        return client.getPage(self.getHTTP("one")
            ).addCallback(self.assertEqual, b"FOUND IT!"
            )


class CookieTestCase(unittest.TestCase):
    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")

    def setUp(self):
        root = Data(b'El toro!', b'text/plain')
        root.putChild(b"cookiemirror", CookieMirrorResource())
        root.putChild(b"rawcookiemirror", RawCookieMirrorResource())
        site = server.Site(root, timeout=None)
        self.port = self._listen(site)
        self.portno = self.port.getHost().port

    def tearDown(self):
        return self.port.stopListening()

    def getHTTP(self, path):
        return networkString("http://127.0.0.1:%d/%s" % (self.portno, path))

    def testNoCookies(self):
        return client.getPage(self.getHTTP("cookiemirror")
            ).addCallback(self.assertEqual, b"[]"
            )

    def testSomeCookies(self):
        cookies = {b'foo': b'bar', b'baz': b'quux'}
        return client.getPage(self.getHTTP("cookiemirror"), cookies=cookies
            ).addCallback(self.assertEqual, b"[('baz', 'quux'), ('foo', 'bar')]"
            )

    def testRawNoCookies(self):
        return client.getPage(self.getHTTP("rawcookiemirror")
            ).addCallback(self.assertEqual, b"None"
            )

    def testRawSomeCookies(self):
        cookies = {b'foo': b'bar', b'baz': b'quux'}
        return client.getPage(self.getHTTP("rawcookiemirror"), cookies=cookies
            ).addCallback(self.assertIn,
                          (b"'foo=bar; baz=quux'", b"'baz=quux; foo=bar'")
            )

    def testCookieHeaderParsing(self):
        factory = client.HTTPClientFactory(b'http://foo.example.com/')
        proto = factory.buildProtocol('127.42.42.42')
        transport = StringTransport()
        proto.makeConnection(transport)
        for line in [
            b'200 Ok',
            b'Squash: yes',
            b'Hands: stolen',
            b'Set-Cookie: CUSTOMER=WILE_E_COYOTE; path=/; expires=Wednesday, 09-Nov-99 23:12:40 GMT',
            b'Set-Cookie: PART_NUMBER=ROCKET_LAUNCHER_0001; path=/',
            b'Set-Cookie: SHIPPING=FEDEX; path=/foo',
            b'',
            b'body',
            b'more body',
            ]:
            proto.dataReceived(line + b'\r\n')
        self.assertEqual(transport.value(),
                         b'GET / HTTP/1.0\r\n'
                         b'Host: foo.example.com\r\n'
                         b'User-Agent: Twisted PageGetter\r\n'
                         b'\r\n')
        self.assertEqual(factory.cookies,
                          {
            b'CUSTOMER': b'WILE_E_COYOTE',
            b'PART_NUMBER': b'ROCKET_LAUNCHER_0001',
            b'SHIPPING': b'FEDEX',
            })



class TestHostHeader(unittest.TestCase):
    """
    Test that L{HTTPClientFactory} includes the port in the host header
    if needed.
    """

    def _getHost(self, bytes):
        """
        Retrieve the value of the I{Host} header from the serialized
        request given by C{bytes}.
        """
        for line in bytes.split(b'\r\n'):
            try:
                name, value = line.split(b':', 1)
                if name.strip().lower() == b'host':
                    return value.strip()
            except ValueError:
                pass


    def test_HTTPDefaultPort(self):
        """
        No port should be included in the host header when connecting to the
        default HTTP port.
        """
        factory = client.HTTPClientFactory(b'http://foo.example.com/')
        proto = factory.buildProtocol(b'127.42.42.42')
        proto.makeConnection(StringTransport())
        self.assertEqual(self._getHost(proto.transport.value()),
                          b'foo.example.com')


    def test_HTTPPort80(self):
        """
        No port should be included in the host header when connecting to the
        default HTTP port even if it is in the URL.
        """
        factory = client.HTTPClientFactory(b'http://foo.example.com:80/')
        proto = factory.buildProtocol('127.42.42.42')
        proto.makeConnection(StringTransport())
        self.assertEqual(self._getHost(proto.transport.value()),
                          b'foo.example.com')


    def test_HTTPNotPort80(self):
        """
        The port should be included in the host header when connecting to the
        a non default HTTP port.
        """
        factory = client.HTTPClientFactory(b'http://foo.example.com:8080/')
        proto = factory.buildProtocol('127.42.42.42')
        proto.makeConnection(StringTransport())
        self.assertEqual(self._getHost(proto.transport.value()),
                          b'foo.example.com:8080')


    def test_HTTPSDefaultPort(self):
        """
        No port should be included in the host header when connecting to the
        default HTTPS port.
        """
        factory = client.HTTPClientFactory(b'https://foo.example.com/')
        proto = factory.buildProtocol('127.42.42.42')
        proto.makeConnection(StringTransport())
        self.assertEqual(self._getHost(proto.transport.value()),
                          b'foo.example.com')


    def test_HTTPSPort443(self):
        """
        No port should be included in the host header when connecting to the
        default HTTPS port even if it is in the URL.
        """
        factory = client.HTTPClientFactory(b'https://foo.example.com:443/')
        proto = factory.buildProtocol('127.42.42.42')
        proto.makeConnection(StringTransport())
        self.assertEqual(self._getHost(proto.transport.value()),
                          b'foo.example.com')


    def test_HTTPSNotPort443(self):
        """
        The port should be included in the host header when connecting to the
        a non default HTTPS port.
        """
        factory = client.HTTPClientFactory(b'http://foo.example.com:8080/')
        proto = factory.buildProtocol('127.42.42.42')
        proto.makeConnection(StringTransport())
        self.assertEqual(self._getHost(proto.transport.value()),
                          b'foo.example.com:8080')


if ssl is None or not hasattr(ssl, 'DefaultOpenSSLContextFactory'):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "OpenSSL not present"

if not interfaces.IReactorSSL(reactor, None):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "Reactor doesn't support SSL"
