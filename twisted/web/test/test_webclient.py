# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.client}.
"""

import os

from urlparse import urlparse

from twisted.trial import unittest
from twisted.web import server, static, client, error, util, resource
from twisted.internet import reactor, defer, interfaces
from twisted.python.filepath import FilePath
from twisted.protocols.policies import WrappingFactory
from twisted.test.proto_helpers import StringTransport

try:
    from twisted.internet import ssl
except:
    ssl = None


class ForeverTakingResource(resource.Resource):
    def render(self, request):
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



class ParseUrlTestCase(unittest.TestCase):
    """
    Test URL parsing facility and defaults values.
    """

    def testParse(self):
        scheme, host, port, path = client._parse("http://127.0.0.1/")
        self.assertEquals(path, "/")
        self.assertEquals(port, 80)
        scheme, host, port, path = client._parse("https://127.0.0.1/")
        self.assertEquals(path, "/")
        self.assertEquals(port, 443)
        scheme, host, port, path = client._parse("http://spam:12345/")
        self.assertEquals(port, 12345)
        scheme, host, port, path = client._parse("http://foo ")
        self.assertEquals(host, "foo")
        self.assertEquals(path, "/")
        scheme, host, port, path = client._parse("http://egg:7890")
        self.assertEquals(port, 7890)
        self.assertEquals(host, "egg")
        self.assertEquals(path, "/")


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
        self.assertTrue(isinstance(scheme, str))
        self.assertTrue(isinstance(host, str))
        self.assertTrue(isinstance(path, str))



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
        name = self.mktemp()
        os.mkdir(name)
        FilePath(name).child("file").setContent("0123456789")
        r = static.File(name)
        r.putChild("redirect", util.Redirect("/file"))
        self.infiniteRedirectResource = CountingRedirect("/infiniteRedirect")
        r.putChild("infiniteRedirect", self.infiniteRedirectResource)
        r.putChild("wait", ForeverTakingResource())
        r.putChild("error", ErrorResource())
        r.putChild("nolength", NoLengthResource())
        r.putChild("host", HostHeaderResource())
        r.putChild("payload", PayloadResource())
        r.putChild("broken", BrokenDownloadResource())
        self.site = server.Site(r, timeout=None)
        self.wrapper = WrappingFactory(self.site)
        self.port = self._listen(self.wrapper)
        self.portno = self.port.getHost().port

    def tearDown(self):
        return self.port.stopListening()

    def getURL(self, path):
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    def testPayload(self):
        s = "0123456789" * 10
        return client.getPage(self.getURL("payload"), postdata=s
            ).addCallback(self.assertEquals, s
            )

    def testBrokenDownload(self):
        # test what happens when download gets disconnected in the middle
        d = client.getPage(self.getURL("broken"))
        d = self.assertFailure(d, client.PartialDownloadError)
        d.addCallback(lambda exc: self.assertEquals(exc.response, "abc"))
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


    def test_getPageHead(self):
        """
        L{client.getPage} returns a L{Deferred} which is called back with
        the empty string if the method is C{HEAD} and there is a successful
        response code.
        """
        def getPage(method):
            return client.getPage(self.getURL("file"), method=method)
        return defer.gatherResults([
            getPage("head").addCallback(self.assertEqual, ""),
            getPage("HEAD").addCallback(self.assertEqual, "")])


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
        finished = self.assertFailure(
            client.getPage(self.getURL("wait"), timeout=0.000001),
            defer.TimeoutError)
        def cleanup(passthrough):
            # Clean up the server which is hanging around not doing
            # anything.
            connected = self.wrapper.protocols.keys()
            # There might be nothing here if the server managed to already see
            # that the connection was lost.
            if connected:
                connected[0].transport.loseConnection()
            return passthrough
        finished.addBoth(cleanup)
        return finished


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
            self.assertEquals(f._redirectCount, 20)
            self.assertEquals(self.infiniteRedirectResource.count, 20)

        f = client._makeGetterFactory(
            self.getURL('infiniteRedirect'),
            client.HTTPClientFactory,
            redirectLimit=20)
        d = self.assertFailure(f.deferred, error.InfiniteRedirection)
        d.addCallback(checkRedirectCount)
        return d


    def testPartial(self):
        name = self.mktemp()
        f = open(name, "wb")
        f.write("abcd")
        f.close()

        downloads = []
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
        d = defer.Deferred()
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

if ssl is None or not hasattr(ssl, 'DefaultOpenSSLContextFactory'):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "OpenSSL not present"

if not interfaces.IReactorSSL(reactor, None):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "Reactor doesn't support SSL"
