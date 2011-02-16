# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.client}.
"""

import os
from errno import ENOSPC

from urlparse import urlparse

from twisted.trial import unittest
from twisted.web import server, static, client, error, util, resource, http_headers
from twisted.internet import reactor, defer, interfaces
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.python.log import msg
from twisted.protocols.policies import WrappingFactory
from twisted.test.proto_helpers import StringTransport
from twisted.test.proto_helpers import MemoryReactor
from twisted.internet.address import IPv4Address
from twisted.internet.task import Clock
from twisted.internet.error import ConnectionRefusedError
from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred, succeed
from twisted.web.client import Request
from twisted.web._newclient import HTTP11ClientProtocol
from twisted.web.error import SchemeNotSupported

try:
    from twisted.internet import ssl
except:
    ssl = None
else:
    from OpenSSL.SSL import ContextType


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
            return "OK Thnx!"
        else:
            self.lastMethod = request.method
            code = int(request.args['code'][0])
            return self.redirectTo(self.url, request, code)


    def getChild(self, name, request):
        return self


    def redirectTo(self, url, request, code):
        request.setResponseCode(code)
        request.setHeader("location", url)
        return "OK Bye!"



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
            request.write('some bytes')
        return server.NOT_DONE_YET


class CookieMirrorResource(resource.Resource):
    def render(self, request):
        l = []
        for k,v in request.received_cookies.items():
            l.append((k, v))
        l.sort()
        return repr(l)

class RawCookieMirrorResource(resource.Resource):
    def render(self, request):
        return repr(request.getHeader('cookie'))

class ErrorResource(resource.Resource):

    def render(self, request):
        request.setResponseCode(401)
        if request.args.get("showlength"):
            request.setHeader("content-length", "0")
        return ""

class NoLengthResource(resource.Resource):

    def render(self, request):
        return "nolength"



class HostHeaderResource(resource.Resource):
    """
    A testing resource which renders itself as the value of the host header
    from the request.
    """
    def render(self, request):
        return request.received_headers['host']



class PayloadResource(resource.Resource):
    """
    A testing resource which renders itself as the contents of the request body
    as long as the request body is 100 bytes long, otherwise which renders
    itself as C{"ERROR"}.
    """
    def render(self, request):
        data = request.content.read()
        contentLength = request.received_headers['content-length']
        if len(data) != 100 or int(contentLength) != 100:
            return "ERROR"
        return data



class BrokenDownloadResource(resource.Resource):

    def render(self, request):
        # only sends 3 bytes even though it claims to send 5
        request.setHeader("content-length", "5")
        request.write('abc')
        return ''

class CountingRedirect(util.Redirect):
    """
    A L{util.Redirect} resource that keeps track of the number of times the
    resource has been accessed.
    """
    def __init__(self, *a, **kw):
        util.Redirect.__init__(self, *a, **kw)
        self.count = 0

    def render(self, request):
        self.count += 1
        return util.Redirect.render(self, request)


class CountingResource(resource.Resource):
    """
    A resource that keeps track of the number of times it has been accessed.
    """
    def __init__(self):
        resource.Resource.__init__(self)
        self.count = 0

    def render(self, request):
        self.count += 1
        return "Success"


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
            client._parse('http://127.0.0.1/'),
            ('http', '127.0.0.1', 80, '/'))

        # The default port for HTTPS is 443.
        self.assertEqual(
            client._parse('https://127.0.0.1/'),
            ('https', '127.0.0.1', 443, '/'))

        # Specifying a port.
        self.assertEqual(
            client._parse('http://spam:12345/'),
            ('http', 'spam', 12345, '/'))

        # Weird (but commonly accepted) structure uses default port.
        self.assertEqual(
            client._parse('http://spam:/'),
            ('http', 'spam', 80, '/'))

        # Spaces in the hostname are trimmed, the default path is /.
        self.assertEqual(
            client._parse('http://foo '),
            ('http', 'foo', 80, '/'))


    def test_externalUnicodeInterference(self):
        """
        L{client._parse} should return C{str} for the scheme, host, and path
        elements of its return tuple, even when passed an URL which has
        previously been passed to L{urlparse} as a C{unicode} string.
        """
        badInput = u'http://example.com/path'
        goodInput = badInput.encode('ascii')
        urlparse(badInput)
        scheme, host, port, path = client._parse(goodInput)
        self.assertIsInstance(scheme, str)
        self.assertIsInstance(host, str)
        self.assertIsInstance(path, str)



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
            'http://foo/bar',
            agent="foobar",
            cookies={'baz': 'quux'},
            postdata="some data",
            headers={
                'Host': 'example.net',
                'User-Agent': 'fooble',
                'Cookie': 'blah blah',
                'Content-Length': '12981',
                'Useful': 'value'})
        transport = StringTransport()
        protocol = client.HTTPPageGetter()
        protocol.factory = factory
        protocol.makeConnection(transport)
        self.assertEqual(
            transport.value(),
            "GET /bar HTTP/1.0\r\n"
            "Host: example.net\r\n"
            "User-Agent: foobar\r\n"
            "Content-Length: 9\r\n"
            "Useful: value\r\n"
            "connection: close\r\n"
            "Cookie: blah blah; baz=quux\r\n"
            "\r\n"
            "some data")



class WebClientTestCase(unittest.TestCase):
    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")

    def setUp(self):
        self.cleanupServerConnections = 0
        name = self.mktemp()
        os.mkdir(name)
        FilePath(name).child("file").setContent("0123456789")
        r = static.File(name)
        r.putChild("redirect", util.Redirect("/file"))
        self.infiniteRedirectResource = CountingRedirect("/infiniteRedirect")
        r.putChild("infiniteRedirect", self.infiniteRedirectResource)
        r.putChild("wait", ForeverTakingResource())
        r.putChild("write-then-wait", ForeverTakingResource(write=True))
        r.putChild("error", ErrorResource())
        r.putChild("nolength", NoLengthResource())
        r.putChild("host", HostHeaderResource())
        r.putChild("payload", PayloadResource())
        r.putChild("broken", BrokenDownloadResource())
        r.putChild("cookiemirror", CookieMirrorResource())

        self.afterFoundGetCounter = CountingResource()
        r.putChild("afterFoundGetCounter", self.afterFoundGetCounter)
        r.putChild("afterFoundGetRedirect", util.Redirect("/afterFoundGetCounter"))

        miscasedHead = static.Data("miscased-head GET response content", "major/minor")
        miscasedHead.render_Head = lambda request: "miscased-head content"
        r.putChild("miscased-head", miscasedHead)

        self.extendedRedirect = ExtendedRedirect('/extendedRedirect')
        r.putChild("extendedRedirect", self.extendedRedirect)
        self.site = server.Site(r, timeout=None)
        self.wrapper = WrappingFactory(self.site)
        self.port = self._listen(self.wrapper)
        self.portno = self.port.getHost().port

    def tearDown(self):
        # If the test indicated it might leave some server-side connections
        # around, clean them up.
        connections = self.wrapper.protocols.keys()
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
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    def testPayload(self):
        s = "0123456789" * 10
        return client.getPage(self.getURL("payload"), postdata=s
            ).addCallback(self.assertEquals, s
            )


    def test_getPageBrokenDownload(self):
        """
        If the connection is closed before the number of bytes indicated by
        I{Content-Length} have been received, the L{Deferred} returned by
        L{getPage} fails with L{PartialDownloadError}.
        """
        d = client.getPage(self.getURL("broken"))
        d = self.assertFailure(d, client.PartialDownloadError)
        d.addCallback(lambda exc: self.assertEquals(exc.response, "abc"))
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
            self.assertEquals(response.status, "200")
            self.assertEquals(response.message, "OK")
            return response
        d.addCallback(checkResponse)

        def cbFailed(ignored):
            self.assertEquals(path.getContent(), "abc")
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
            self.assertEquals(len(self.flushLoggedErrors(IOError)), 1)
        d.addCallback(cbFailed)
        return d


    def testHostHeader(self):
        # if we pass Host header explicitly, it should be used, otherwise
        # it should extract from url
        return defer.gatherResults([
            client.getPage(self.getURL("host")).addCallback(self.assertEquals, "127.0.0.1"),
            client.getPage(self.getURL("host"), headers={"Host": "www.example.com"}).addCallback(self.assertEquals, "www.example.com")])


    def test_getPage(self):
        """
        L{client.getPage} returns a L{Deferred} which is called back with
        the body of the response if the default method B{GET} is used.
        """
        d = client.getPage(self.getURL("file"))
        d.addCallback(self.assertEquals, "0123456789")
        return d


    def test_getPageHEAD(self):
        """
        L{client.getPage} returns a L{Deferred} which is called back with
        the empty string if the method is I{HEAD} and there is a successful
        response code.
        """
        d = client.getPage(self.getURL("file"), method="HEAD")
        d.addCallback(self.assertEquals, "")
        return d



    def test_getPageNotQuiteHEAD(self):
        """
        If the request method is a different casing of I{HEAD} (ie, not all
        capitalized) then it is not a I{HEAD} request and the response body
        is returned.
        """
        d = client.getPage(self.getURL("miscased-head"), method='Head')
        d.addCallback(self.assertEquals, "miscased-head content")
        return d


    def test_timeoutNotTriggering(self):
        """
        When a non-zero timeout is passed to L{getPage} and the page is
        retrieved before the timeout period elapses, the L{Deferred} is
        called back with the contents of the page.
        """
        d = client.getPage(self.getURL("host"), timeout=100)
        d.addCallback(self.assertEquals, "127.0.0.1")
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
        downloadData = [("file", self.mktemp(), "0123456789"),
                        ("nolength", self.mktemp(), "nolength")]

        for (url, name, data) in downloadData:
            d = client.downloadPage(self.getURL(url), name)
            d.addCallback(self._cbDownloadPageTest, data, name)
            downloads.append(d)
        return defer.gatherResults(downloads)

    def _cbDownloadPageTest(self, ignored, data, name):
        bytes = file(name, "rb").read()
        self.assertEquals(bytes, data)

    def testDownloadPageError1(self):
        class errorfile:
            def write(self, data):
                raise IOError, "badness happened during write"
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
                raise IOError, "badness happened during close"
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
        os.chmod("unwritable", 0700)
        os.unlink("unwritable")
        return ignored

    def _downloadTest(self, method):
        dl = []
        for (url, code) in [("nosuchfile", "404"), ("error", "401"),
                            ("error?showlength=1", "401")]:
            d = method(url)
            d = self.assertFailure(d, error.Error)
            d.addCallback(lambda exc, code=code: self.assertEquals(exc.args[0], code))
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
        reactor.connectTCP(host, port, factory)
        return factory.deferred.addCallback(self._cbFactoryInfo, factory)

    def _cbFactoryInfo(self, ignoredResult, factory):
        self.assertEquals(factory.status, '200')
        self.assert_(factory.version.startswith('HTTP/'))
        self.assertEquals(factory.message, 'OK')
        self.assertEquals(factory.response_headers['content-length'][0], '10')


    def testRedirect(self):
        return client.getPage(self.getURL("redirect")).addCallback(self._cbRedirect)

    def _cbRedirect(self, pageData):
        self.assertEquals(pageData, "0123456789")
        d = self.assertFailure(
            client.getPage(self.getURL("redirect"), followRedirect=0),
            error.PageRedirect)
        d.addCallback(self._cbCheckLocation)
        return d

    def _cbCheckLocation(self, exc):
        self.assertEquals(exc.location, "/file")


    def test_infiniteRedirection(self):
        """
        When more than C{redirectLimit} HTTP redirects are encountered, the
        page request fails with L{InfiniteRedirection}.
        """
        def checkRedirectCount(*a):
            self.assertEquals(f._redirectCount, 13)
            self.assertEquals(self.infiniteRedirectResource.count, 13)

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
        f = client.HTTPClientFactory(url, followRedirect=True, method="POST")
        self.assertFalse(
            f.afterFoundGet,
            "By default, afterFoundGet must be disabled")

        def gotPage(page):
            self.assertEquals(
                self.extendedRedirect.lastMethod,
                "GET",
                "With afterFoundGet, the HTTP method must change to GET")

        d = client.getPage(
            url, followRedirect=True, afterFoundGet=True, method="POST")
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
            self.assertEquals(
                self.extendedRedirect.lastMethod,
                "GET",
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
            self.assertEquals(self.afterFoundGetCounter.count, 1)

        url = self.getURL('afterFoundGetRedirect')
        d = client.getPage(
            url, followRedirect=True, afterFoundGet=True, method="POST")
        d.addCallback(checkRedirectCount)
        return d


    def testPartial(self):
        name = self.mktemp()
        f = open(name, "wb")
        f.write("abcd")
        f.close()

        partialDownload = [(True, "abcd456789"),
                           (True, "abcd456789"),
                           (False, "0123456789")]

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
        self.assertEquals(bytes, expectedData)


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
            self.assertEquals(factory.status, '200')
            self.assertEquals(factory.response_headers['content-type'][0], 'text/html')
            self.assertEquals(factory.response_headers['content-length'][0], '10')
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
            cookies={'foo': 'bar'})
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
            self.assertEquals(f._redirectCount, 7)
            self.assertEquals(self.infiniteRedirectResource.count, 7)

        f = client._makeGetterFactory(
            self.getURL('infiniteRedirect'),
            client.HTTPDownloader,
            fileOrName=self.mktemp(),
            redirectLimit=7)
        d = self.assertFailure(f.deferred, error.InfiniteRedirection)
        d.addCallback(checkRedirectCount)
        return d



class WebClientSSLTestCase(WebClientTestCase):
    def _listen(self, site):
        from twisted import test
        return reactor.listenSSL(0, site,
                                 contextFactory=ssl.DefaultOpenSSLContextFactory(
            FilePath(test.__file__).sibling('server.pem').path,
            FilePath(test.__file__).sibling('server.pem').path,
            ),
                                 interface="127.0.0.1")

    def getURL(self, path):
        return "https://127.0.0.1:%d/%s" % (self.portno, path)

    def testFactoryInfo(self):
        url = self.getURL('file')
        scheme, host, port, path = client._parse(url)
        factory = client.HTTPClientFactory(url)
        reactor.connectSSL(host, port, factory, ssl.ClientContextFactory())
        # The base class defines _cbFactoryInfo correctly for this
        return factory.deferred.addCallback(self._cbFactoryInfo, factory)

class WebClientRedirectBetweenSSLandPlainText(unittest.TestCase):
    def getHTTPS(self, path):
        return "https://127.0.0.1:%d/%s" % (self.tlsPortno, path)

    def getHTTP(self, path):
        return "http://127.0.0.1:%d/%s" % (self.plainPortno, path)

    def setUp(self):
        plainRoot = static.Data('not me', 'text/plain')
        tlsRoot = static.Data('me neither', 'text/plain')

        plainSite = server.Site(plainRoot, timeout=None)
        tlsSite = server.Site(tlsRoot, timeout=None)

        from twisted import test
        self.tlsPort = reactor.listenSSL(0, tlsSite,
                                         contextFactory=ssl.DefaultOpenSSLContextFactory(
            FilePath(test.__file__).sibling('server.pem').path,
            FilePath(test.__file__).sibling('server.pem').path,
            ),
                                         interface="127.0.0.1")
        self.plainPort = reactor.listenTCP(0, plainSite, interface="127.0.0.1")

        self.plainPortno = self.plainPort.getHost().port
        self.tlsPortno = self.tlsPort.getHost().port

        plainRoot.putChild('one', util.Redirect(self.getHTTPS('two')))
        tlsRoot.putChild('two', util.Redirect(self.getHTTP('three')))
        plainRoot.putChild('three', util.Redirect(self.getHTTPS('four')))
        tlsRoot.putChild('four', static.Data('FOUND IT!', 'text/plain'))

    def tearDown(self):
        ds = map(defer.maybeDeferred,
                 [self.plainPort.stopListening, self.tlsPort.stopListening])
        return defer.gatherResults(ds)

    def testHoppingAround(self):
        return client.getPage(self.getHTTP("one")
            ).addCallback(self.assertEquals, "FOUND IT!"
            )

class FakeTransport:
    disconnecting = False
    def __init__(self):
        self.data = []
    def write(self, stuff):
        self.data.append(stuff)

class CookieTestCase(unittest.TestCase):
    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")

    def setUp(self):
        root = static.Data('El toro!', 'text/plain')
        root.putChild("cookiemirror", CookieMirrorResource())
        root.putChild("rawcookiemirror", RawCookieMirrorResource())
        site = server.Site(root, timeout=None)
        self.port = self._listen(site)
        self.portno = self.port.getHost().port

    def tearDown(self):
        return self.port.stopListening()

    def getHTTP(self, path):
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    def testNoCookies(self):
        return client.getPage(self.getHTTP("cookiemirror")
            ).addCallback(self.assertEquals, "[]"
            )

    def testSomeCookies(self):
        cookies = {'foo': 'bar', 'baz': 'quux'}
        return client.getPage(self.getHTTP("cookiemirror"), cookies=cookies
            ).addCallback(self.assertEquals, "[('baz', 'quux'), ('foo', 'bar')]"
            )

    def testRawNoCookies(self):
        return client.getPage(self.getHTTP("rawcookiemirror")
            ).addCallback(self.assertEquals, "None"
            )

    def testRawSomeCookies(self):
        cookies = {'foo': 'bar', 'baz': 'quux'}
        return client.getPage(self.getHTTP("rawcookiemirror"), cookies=cookies
            ).addCallback(self.assertEquals, "'foo=bar; baz=quux'"
            )

    def testCookieHeaderParsing(self):
        factory = client.HTTPClientFactory('http://foo.example.com/')
        proto = factory.buildProtocol('127.42.42.42')
        proto.transport = FakeTransport()
        proto.connectionMade()
        for line in [
            '200 Ok',
            'Squash: yes',
            'Hands: stolen',
            'Set-Cookie: CUSTOMER=WILE_E_COYOTE; path=/; expires=Wednesday, 09-Nov-99 23:12:40 GMT',
            'Set-Cookie: PART_NUMBER=ROCKET_LAUNCHER_0001; path=/',
            'Set-Cookie: SHIPPING=FEDEX; path=/foo',
            '',
            'body',
            'more body',
            ]:
            proto.dataReceived(line + '\r\n')
        self.assertEquals(proto.transport.data,
                          ['GET / HTTP/1.0\r\n',
                           'Host: foo.example.com\r\n',
                           'User-Agent: Twisted PageGetter\r\n',
                           '\r\n'])
        self.assertEquals(factory.cookies,
                          {
            'CUSTOMER': 'WILE_E_COYOTE',
            'PART_NUMBER': 'ROCKET_LAUNCHER_0001',
            'SHIPPING': 'FEDEX',
            })



class StubHTTPProtocol(Protocol):
    """
    A protocol like L{HTTP11ClientProtocol} but which does not actually know
    HTTP/1.1 and only collects requests in a list.

    @ivar requests: A C{list} of two-tuples.  Each time a request is made, a
        tuple consisting of the request and the L{Deferred} returned from the
        request method is appended to this list.
    """
    def __init__(self):
        self.requests = []


    def request(self, request):
        """
        Capture the given request for later inspection.

        @return: A L{Deferred} which this code will never fire.
        """
        result = Deferred()
        self.requests.append((request, result))
        return result



class AgentTests(unittest.TestCase):
    """
    Tests for the new HTTP client API provided by L{Agent}.
    """
    def setUp(self):
        """
        Create an L{Agent} wrapped around a fake reactor.
        """
        class Reactor(MemoryReactor, Clock):
            def __init__(self):
                MemoryReactor.__init__(self)
                Clock.__init__(self)

        self.reactor = Reactor()
        self.agent = client.Agent(self.reactor)


    def completeConnection(self):
        """
        Do whitebox stuff to finish any outstanding connection attempts the
        agent may have initiated.

        This spins the fake reactor clock just enough to get L{ClientCreator},
        which agent is implemented in terms of, to fire its Deferreds.
        """
        self.reactor.advance(0)


    def test_unsupportedScheme(self):
        """
        L{Agent.request} returns a L{Deferred} which fails with
        L{SchemeNotSupported} if the scheme of the URI passed to it is not
        C{'http'}.
        """
        return self.assertFailure(
            self.agent.request('GET', 'mailto:alice@example.com'),
            SchemeNotSupported)


    def test_connectionFailed(self):
        """
        The L{Deferred} returned by L{Agent.request} fires with a L{Failure} if
        the TCP connection attempt fails.
        """
        result = self.agent.request('GET', 'http://foo/')

        # Cause the connection to be refused
        host, port, factory = self.reactor.tcpClients.pop()[:3]
        factory.clientConnectionFailed(None, Failure(ConnectionRefusedError()))
        self.completeConnection()

        return self.assertFailure(result, ConnectionRefusedError)


    def test_connectHTTP(self):
        """
        L{Agent._connect} uses C{connectTCP} to set up a connection to
        a server when passed a scheme of C{'http'} and returns a
        L{Deferred} which fires (when that connection is established)
        with the protocol associated with that connection.
        """
        expectedHost = 'example.com'
        expectedPort = 1234
        d = self.agent._connect('http', expectedHost, expectedPort)
        host, port, factory = self.reactor.tcpClients.pop()[:3]
        self.assertEquals(host, expectedHost)
        self.assertEquals(port, expectedPort)
        protocol = factory.buildProtocol(IPv4Address('TCP', '10.0.0.1', port))
        self.assertIsInstance(protocol, HTTP11ClientProtocol)
        self.completeConnection()
        d.addCallback(self.assertIdentical, protocol)
        return d


    def test_connectHTTPS(self):
        """
        L{Agent._connect} uses C{connectSSL} to set up a connection to
        a server when passed a scheme of C{'https'} and returns a
        L{Deferred} which fires (when that connection is established)
        with the protocol associated with that connection.
        """
        expectedHost = 'example.com'
        expectedPort = 4321
        d = self.agent._connect('https', expectedHost, expectedPort)
        host, port, factory, contextFactory = self.reactor.sslClients.pop()[:4]
        self.assertEquals(host, expectedHost)
        self.assertEquals(port, expectedPort)
        context = contextFactory.getContext()

        # This is a pretty weak assertion.  It's true that the context must be
        # an instance of OpenSSL.SSL.Context, Unfortunately these are pretty
        # opaque and there's not much more than checking its type that we could
        # do here.  It would be nice if the SSL APIs involved more testable (ie,
        # inspectable) objects.
        self.assertIsInstance(context, ContextType)

        protocol = factory.buildProtocol(IPv4Address('TCP', '10.0.0.1', port))
        self.assertIsInstance(protocol, HTTP11ClientProtocol)
        self.completeConnection()
        d.addCallback(self.assertIdentical, protocol)
        return d
    if ssl is None:
        test_connectHTTPS.skip = "OpenSSL not present"


    def test_connectHTTPSCustomContextFactory(self):
        """
        If a context factory is passed to L{Agent.__init__} it will be used to
        determine the SSL parameters for HTTPS requests.  When an HTTPS request
        is made, the hostname and port number of the request URL will be passed
        to the context factory's C{getContext} method.  The resulting context
        object will be used to establish the SSL connection.
        """
        expectedHost = 'example.org'
        expectedPort = 20443
        expectedContext = object()

        contextArgs = []
        class StubWebContextFactory(object):
            def getContext(self, hostname, port):
                contextArgs.append((hostname, port))
                return expectedContext

        agent = client.Agent(self.reactor, StubWebContextFactory())
        d = agent._connect('https', expectedHost, expectedPort)
        host, port, factory, contextFactory = self.reactor.sslClients.pop()[:4]
        context = contextFactory.getContext()
        self.assertEquals(context, expectedContext)
        self.assertEquals(contextArgs, [(expectedHost, expectedPort)])
        protocol = factory.buildProtocol(IPv4Address('TCP', '10.0.0.1', port))
        self.assertIsInstance(protocol, HTTP11ClientProtocol)
        self.completeConnection()
        d.addCallback(self.assertIdentical, protocol)
        return d


    def _dummyConnect(self, scheme, host, port):
        """
        Fake implementation of L{Agent._connect} which synchronously
        succeeds with an instance of L{StubHTTPProtocol} for ease of
        testing.
        """
        protocol = StubHTTPProtocol()
        protocol.makeConnection(None)
        self.protocol = protocol
        return succeed(protocol)


    def test_request(self):
        """
        L{Agent.request} establishes a new connection to the host indicated by
        the host part of the URI passed to it and issues a request using the
        method, the path portion of the URI, the headers, and the body producer
        passed to it.  It returns a L{Deferred} which fires with a L{Response}
        from the server.
        """
        self.agent._connect = self._dummyConnect

        headers = http_headers.Headers({'foo': ['bar']})
        # Just going to check the body for identity, so it doesn't need to be
        # real.
        body = object()
        self.agent.request(
            'GET', 'http://example.com:1234/foo?bar', headers, body)

        protocol = self.protocol

        # The request should be issued.
        self.assertEquals(len(protocol.requests), 1)
        req, res = protocol.requests.pop()
        self.assertIsInstance(req, Request)
        self.assertEquals(req.method, 'GET')
        self.assertEquals(req.uri, '/foo?bar')
        self.assertEquals(
            req.headers,
            http_headers.Headers({'foo': ['bar'],
                                  'host': ['example.com:1234']}))
        self.assertIdentical(req.bodyProducer, body)


    def test_hostProvided(self):
        """
        If C{None} is passed to L{Agent.request} for the C{headers}
        parameter, a L{Headers} instance is created for the request and a
        I{Host} header added to it.
        """
        self.agent._connect = self._dummyConnect

        self.agent.request('GET', 'http://example.com/foo')

        protocol = self.protocol

        # The request should have been issued with a host header based on
        # the request URL.
        self.assertEquals(len(protocol.requests), 1)
        req, res = protocol.requests.pop()
        self.assertEquals(req.headers.getRawHeaders('host'), ['example.com'])


    def test_hostOverride(self):
        """
        If the headers passed to L{Agent.request} includes a value for the
        I{Host} header, that value takes precedence over the one which would
        otherwise be automatically provided.
        """
        self.agent._connect = self._dummyConnect

        headers = http_headers.Headers({'foo': ['bar'], 'host': ['quux']})
        body = object()
        self.agent.request(
            'GET', 'http://example.com/baz', headers, body)

        protocol = self.protocol

        # The request should have been issued with the host header specified
        # above, not one based on the request URI.
        self.assertEquals(len(protocol.requests), 1)
        req, res = protocol.requests.pop()
        self.assertEquals(req.headers.getRawHeaders('host'), ['quux'])


    def test_headersUnmodified(self):
        """
        If a I{Host} header must be added to the request, the L{Headers}
        instance passed to L{Agent.request} is not modified.
        """
        self.agent._connect = self._dummyConnect

        headers = http_headers.Headers()
        body = object()
        self.agent.request(
            'GET', 'http://example.com/foo', headers, body)

        protocol = self.protocol

        # The request should have been issued.
        self.assertEquals(len(protocol.requests), 1)
        # And the headers object passed in should not have changed.
        self.assertEquals(headers, http_headers.Headers())


    def test_hostValueStandardHTTP(self):
        """
        When passed a scheme of C{'http'} and a port of C{80},
        L{Agent._computeHostValue} returns a string giving just the
        host name passed to it.
        """
        self.assertEquals(
            self.agent._computeHostValue('http', 'example.com', 80),
            'example.com')


    def test_hostValueNonStandardHTTP(self):
        """
        When passed a scheme of C{'http'} and a port other than C{80},
        L{Agent._computeHostValue} returns a string giving the host
        passed to it joined together with the port number by C{":"}.
        """
        self.assertEquals(
            self.agent._computeHostValue('http', 'example.com', 54321),
            'example.com:54321')


    def test_hostValueStandardHTTPS(self):
        """
        When passed a scheme of C{'https'} and a port of C{443},
        L{Agent._computeHostValue} returns a string giving just the
        host name passed to it.
        """
        self.assertEquals(
            self.agent._computeHostValue('https', 'example.com', 443),
            'example.com')


    def test_hostValueNonStandardHTTPS(self):
        """
        When passed a scheme of C{'https'} and a port other than
        C{443}, L{Agent._computeHostValue} returns a string giving the
        host passed to it joined together with the port number by
        C{":"}.
        """
        self.assertEquals(
            self.agent._computeHostValue('https', 'example.com', 54321),
            'example.com:54321')



if ssl is None or not hasattr(ssl, 'DefaultOpenSSLContextFactory'):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "OpenSSL not present"

if not interfaces.IReactorSSL(reactor, None):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "Reactor doesn't support SSL"
