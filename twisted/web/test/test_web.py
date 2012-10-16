# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for various parts of L{twisted.web}.
"""

from cStringIO import StringIO
import zlib

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.internet import reactor
from twisted.internet.address import IPv4Address
from twisted.internet.defer import Deferred
from twisted.web import server, resource, util
from twisted.internet import defer, interfaces, task
from twisted.web import iweb, http, http_headers, error
from twisted.web.static import Data
from twisted.python import log

from twisted.web.test.requesthelper import DummyChannel, DummyRequest


class ResourceTestCase(unittest.TestCase):
    def testListEntities(self):
        r = resource.Resource()
        self.assertEqual([], r.listEntities())


class SimpleResource(resource.Resource):
    """
    @ivar _contentType: C{None} or a C{str} giving the value of the
        I{Content-Type} header in the response this resource will render.  If it
        is C{None}, no I{Content-Type} header will be set in the response.
    """
    def __init__(self, contentType=None):
        resource.Resource.__init__(self)
        self._contentType = contentType


    def render(self, request):
        if self._contentType is not None:
            request.responseHeaders.setRawHeaders(
                "content-type", [self._contentType])

        if http.CACHED in (request.setLastModified(10),
                           request.setETag('MatchingTag')):
            return ''
        else:
            return "correct"


class SiteTest(unittest.TestCase):
    def test_simplestSite(self):
        """
        L{Site.getResourceFor} returns the C{""} child of the root resource it
        is constructed with when processing a request for I{/}.
        """
        sres1 = SimpleResource()
        sres2 = SimpleResource()
        sres1.putChild("",sres2)
        site = server.Site(sres1)
        self.assertIdentical(
            site.getResourceFor(DummyRequest([''])),
            sres2, "Got the wrong resource.")



class SessionTest(unittest.TestCase):
    """
    Tests for L{server.Session}.
    """
    def setUp(self):
        """
        Create a site with one active session using a deterministic, easily
        controlled clock.
        """
        self.clock = task.Clock()
        self.uid = 'unique'
        self.site = server.Site(resource.Resource())
        self.session = server.Session(self.site, self.uid, self.clock)
        self.site.sessions[self.uid] = self.session


    def test_defaultReactor(self):
        """
        If not value is passed to L{server.Session.__init__}, the global
        reactor is used.
        """
        session = server.Session(server.Site(resource.Resource()), '123')
        self.assertIdentical(session._reactor, reactor)


    def test_startCheckingExpiration(self):
        """
        L{server.Session.startCheckingExpiration} causes the session to expire
        after L{server.Session.sessionTimeout} seconds without activity.
        """
        self.session.startCheckingExpiration()

        # Advance to almost the timeout - nothing should happen.
        self.clock.advance(self.session.sessionTimeout - 1)
        self.assertIn(self.uid, self.site.sessions)

        # Advance to the timeout, the session should expire.
        self.clock.advance(1)
        self.assertNotIn(self.uid, self.site.sessions)

        # There should be no calls left over, either.
        self.assertFalse(self.clock.calls)


    def test_expire(self):
        """
        L{server.Session.expire} expires the session.
        """
        self.session.expire()
        # It should be gone from the session dictionary.
        self.assertNotIn(self.uid, self.site.sessions)
        # And there should be no pending delayed calls.
        self.assertFalse(self.clock.calls)


    def test_expireWhileChecking(self):
        """
        L{server.Session.expire} expires the session even if the timeout call
        isn't due yet.
        """
        self.session.startCheckingExpiration()
        self.test_expire()


    def test_notifyOnExpire(self):
        """
        A function registered with L{server.Session.notifyOnExpire} is called
        when the session expires.
        """
        callbackRan = [False]
        def expired():
            callbackRan[0] = True
        self.session.notifyOnExpire(expired)
        self.session.expire()
        self.assertTrue(callbackRan[0])


    def test_touch(self):
        """
        L{server.Session.touch} updates L{server.Session.lastModified} and
        delays session timeout.
        """
        # Make sure it works before startCheckingExpiration
        self.clock.advance(3)
        self.session.touch()
        self.assertEqual(self.session.lastModified, 3)

        # And after startCheckingExpiration
        self.session.startCheckingExpiration()
        self.clock.advance(self.session.sessionTimeout - 1)
        self.session.touch()
        self.clock.advance(self.session.sessionTimeout - 1)
        self.assertIn(self.uid, self.site.sessions)

        # It should have advanced it by just sessionTimeout, no more.
        self.clock.advance(1)
        self.assertNotIn(self.uid, self.site.sessions)


    def test_startCheckingExpirationParameterDeprecated(self):
        """
        L{server.Session.startCheckingExpiration} emits a deprecation warning
        if it is invoked with a parameter.
        """
        self.session.startCheckingExpiration(123)
        warnings = self.flushWarnings([
                self.test_startCheckingExpirationParameterDeprecated])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            "The lifetime parameter to startCheckingExpiration is deprecated "
            "since Twisted 9.0.  See Session.sessionTimeout instead.")


    def test_checkExpiredDeprecated(self):
        """
        L{server.Session.checkExpired} is deprecated.
        """
        self.session.checkExpired()
        warnings = self.flushWarnings([self.test_checkExpiredDeprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            "Session.checkExpired is deprecated since Twisted 9.0; sessions "
            "check themselves now, you don't need to.")
        self.assertEqual(len(warnings), 1)


# Conditional requests:
# If-None-Match, If-Modified-Since

# make conditional request:
#   normal response if condition succeeds
#   if condition fails:
#      response code
#      no body

def httpBody(whole):
    return whole.split('\r\n\r\n', 1)[1]

def httpHeader(whole, key):
    key = key.lower()
    headers = whole.split('\r\n\r\n', 1)[0]
    for header in headers.split('\r\n'):
        if header.lower().startswith(key):
            return header.split(':', 1)[1].strip()
    return None

def httpCode(whole):
    l1 = whole.split('\r\n', 1)[0]
    return int(l1.split()[1])

class ConditionalTest(unittest.TestCase):
    """
    web.server's handling of conditional requests for cache validation.
    """
    def setUp(self):
        self.resrc = SimpleResource()
        self.resrc.putChild('', self.resrc)
        self.resrc.putChild('with-content-type', SimpleResource('image/jpeg'))
        self.site = server.Site(self.resrc)
        self.site.logFile = log.logfile

        # HELLLLLLLLLLP!  This harness is Very Ugly.
        self.channel = self.site.buildProtocol(None)
        self.transport = http.StringTransport()
        self.transport.close = lambda *a, **kw: None
        self.transport.disconnecting = lambda *a, **kw: 0
        self.transport.getPeer = lambda *a, **kw: "peer"
        self.transport.getHost = lambda *a, **kw: "host"
        self.channel.makeConnection(self.transport)


    def tearDown(self):
        self.channel.connectionLost(None)


    def _modifiedTest(self, modifiedSince=None, etag=None):
        """
        Given the value C{modifiedSince} for the I{If-Modified-Since} header or
        the value C{etag} for the I{If-Not-Match} header, verify that a response
        with a 200 code, a default Content-Type, and the resource as the body is
        returned.
        """
        if modifiedSince is not None:
            validator = "If-Modified-Since: " + modifiedSince
        else:
            validator = "If-Not-Match: " + etag
        for line in ["GET / HTTP/1.1", validator, ""]:
            self.channel.lineReceived(line)
        result = self.transport.getvalue()
        self.assertEqual(httpCode(result), http.OK)
        self.assertEqual(httpBody(result), "correct")
        self.assertEqual(httpHeader(result, "Content-Type"), "text/html")


    def test_modified(self):
        """
        If a request is made with an I{If-Modified-Since} header value with
        a timestamp indicating a time before the last modification of the
        requested resource, a 200 response is returned along with a response
        body containing the resource.
        """
        self._modifiedTest(modifiedSince=http.datetimeToString(1))


    def test_unmodified(self):
        """
        If a request is made with an I{If-Modified-Since} header value with a
        timestamp indicating a time after the last modification of the request
        resource, a 304 response is returned along with an empty response body
        and no Content-Type header if the application does not set one.
        """
        for line in ["GET / HTTP/1.1",
                     "If-Modified-Since: " + http.datetimeToString(100), ""]:
            self.channel.lineReceived(line)
        result = self.transport.getvalue()
        self.assertEqual(httpCode(result), http.NOT_MODIFIED)
        self.assertEqual(httpBody(result), "")
        # Since there SHOULD NOT (RFC 2616, section 10.3.5) be any
        # entity-headers, the Content-Type is not set if the application does
        # not explicitly set it.
        self.assertEqual(httpHeader(result, "Content-Type"), None)


    def test_invalidTimestamp(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        cannot be parsed, the header is treated as not having been present
        and a normal 200 response is returned with a response body
        containing the resource.
        """
        self._modifiedTest(modifiedSince="like, maybe a week ago, I guess?")


    def test_invalidTimestampYear(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        contains a string in the year position which is not an integer, the
        header is treated as not having been present and a normal 200
        response is returned with a response body containing the resource.
        """
        self._modifiedTest(modifiedSince="Thu, 01 Jan blah 00:00:10 GMT")


    def test_invalidTimestampTooLongAgo(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        contains a year before the epoch, the header is treated as not
        having been present and a normal 200 response is returned with a
        response body containing the resource.
        """
        self._modifiedTest(modifiedSince="Thu, 01 Jan 1899 00:00:10 GMT")


    def test_invalidTimestampMonth(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        contains a string in the month position which is not a recognized
        month abbreviation, the header is treated as not having been present
        and a normal 200 response is returned with a response body
        containing the resource.
        """
        self._modifiedTest(modifiedSince="Thu, 01 Blah 1970 00:00:10 GMT")


    def test_etagMatchedNot(self):
        """
        If a request is made with an I{If-None-Match} ETag which does not match
        the current ETag of the requested resource, the header is treated as not
        having been present and a normal 200 response is returned with a
        response body containing the resource.
        """
        self._modifiedTest(etag="unmatchedTag")


    def test_etagMatched(self):
        """
        If a request is made with an I{If-None-Match} ETag which does match the
        current ETag of the requested resource, a 304 response is returned along
        with an empty response body.
        """
        for line in ["GET / HTTP/1.1", "If-None-Match: MatchingTag", ""]:
            self.channel.lineReceived(line)
        result = self.transport.getvalue()
        self.assertEqual(httpHeader(result, "ETag"), "MatchingTag")
        self.assertEqual(httpCode(result), http.NOT_MODIFIED)
        self.assertEqual(httpBody(result), "")


    def test_unmodifiedWithContentType(self):
        """
        Similar to L{test_etagMatched}, but the response should include a
        I{Content-Type} header if the application explicitly sets one.

        This I{Content-Type} header SHOULD NOT be present according to RFC 2616,
        section 10.3.5.  It will only be present if the application explicitly
        sets it.
        """
        for line in ["GET /with-content-type HTTP/1.1",
                     "If-None-Match: MatchingTag", ""]:
            self.channel.lineReceived(line)
        result = self.transport.getvalue()
        self.assertEqual(httpCode(result), http.NOT_MODIFIED)
        self.assertEqual(httpBody(result), "")
        self.assertEqual(httpHeader(result, "Content-Type"), "image/jpeg")



class RequestTests(unittest.TestCase):
    """
    Tests for the HTTP request class, L{server.Request}.
    """

    def test_interface(self):
        """
        L{server.Request} instances provide L{iweb.IRequest}.
        """
        self.assertTrue(
            verifyObject(iweb.IRequest, server.Request(DummyChannel(), True)))


    def testChildLink(self):
        request = server.Request(DummyChannel(), 1)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.childLink('baz'), 'bar/baz')
        request = server.Request(DummyChannel(), 1)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar/', 'HTTP/1.0')
        self.assertEqual(request.childLink('baz'), 'baz')

    def testPrePathURLSimple(self):
        request = server.Request(DummyChannel(), 1)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        request.setHost('example.com', 80)
        self.assertEqual(request.prePathURL(), 'http://example.com/foo/bar')

    def testPrePathURLNonDefault(self):
        d = DummyChannel()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('example.com', 81)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'http://example.com:81/foo/bar')

    def testPrePathURLSSLPort(self):
        d = DummyChannel()
        d.transport.port = 443
        request = server.Request(d, 1)
        request.setHost('example.com', 443)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'http://example.com:443/foo/bar')

    def testPrePathURLSSLPortAndSSL(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSL()
        d.transport.port = 443
        request = server.Request(d, 1)
        request.setHost('example.com', 443)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://example.com/foo/bar')

    def testPrePathURLHTTPPortAndSSL(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSL()
        d.transport.port = 80
        request = server.Request(d, 1)
        request.setHost('example.com', 80)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://example.com:80/foo/bar')

    def testPrePathURLSSLNonDefault(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSL()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('example.com', 81)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://example.com:81/foo/bar')

    def testPrePathURLSetSSLHost(self):
        d = DummyChannel()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('foo.com', 81, 1)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://foo.com:81/foo/bar')


    def test_prePathURLQuoting(self):
        """
        L{Request.prePathURL} quotes special characters in the URL segments to
        preserve the original meaning.
        """
        d = DummyChannel()
        request = server.Request(d, 1)
        request.setHost('example.com', 80)
        request.gotLength(0)
        request.requestReceived('GET', '/foo%2Fbar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'http://example.com/foo%2Fbar')



class GzipEncoderTests(unittest.TestCase):

    def setUp(self):
        self.channel = DummyChannel()
        staticResource = Data("Some data", "text/plain")
        wrapped = resource.EncodingResourceWrapper(
            staticResource, [server.GzipEncoderFactory()])
        self.channel.site.resource.putChild("foo", wrapped)


    def test_interfaces(self):
        """
        L{server.GzipEncoderFactory} implements the
        L{iweb._IRequestEncoderFactory} and its C{encoderForRequest} returns an
        instance of L{server._GzipEncoder} which implements
        L{iweb._IRequestEncoder}.
        """
        request = server.Request(self.channel, False)
        request.gotLength(0)
        request.requestHeaders.setRawHeaders("Accept-Encoding",
                                             ["gzip,deflate"])
        factory = server.GzipEncoderFactory()
        self.assertTrue(verifyObject(iweb._IRequestEncoderFactory, factory))

        encoder = factory.encoderForRequest(request)
        self.assertTrue(verifyObject(iweb._IRequestEncoder, encoder))


    def test_encoding(self):
        """
        If the client request passes a I{Accept-Encoding} header which mentions
        gzip, L{server._GzipEncoder} automatically compresses the data.
        """
        request = server.Request(self.channel, False)
        request.gotLength(0)
        request.requestHeaders.setRawHeaders("Accept-Encoding",
                                             ["gzip,deflate"])
        request.requestReceived('GET', '/foo', 'HTTP/1.0')
        data = self.channel.transport.written.getvalue()
        self.assertNotIn("Content-Length", data)
        self.assertIn("Content-Encoding: gzip\r\n", data)
        body = data[data.find("\r\n\r\n") + 4:]
        self.assertEqual("Some data",
                          zlib.decompress(body, 16 + zlib.MAX_WBITS))


    def test_nonEncoding(self):
        """
        L{server.GzipEncoderFactory} doesn't return a L{server._GzipEncoder} if
        the I{Accept-Encoding} header doesn't mention gzip support.
        """
        request = server.Request(self.channel, False)
        request.gotLength(0)
        request.requestHeaders.setRawHeaders("Accept-Encoding",
                                             ["foo,bar"])
        request.requestReceived('GET', '/foo', 'HTTP/1.0')
        data = self.channel.transport.written.getvalue()
        self.assertIn("Content-Length", data)
        self.assertNotIn("Content-Encoding: gzip\r\n", data)
        body = data[data.find("\r\n\r\n") + 4:]
        self.assertEqual("Some data", body)


    def test_multipleAccept(self):
        """
        If there are multiple I{Accept-Encoding} header,
        L{server.GzipEncoderFactory} reads them properly to detect if gzip is
        supported.
        """
        request = server.Request(self.channel, False)
        request.gotLength(0)
        request.requestHeaders.setRawHeaders("Accept-Encoding",
                                             ["deflate", "gzip"])
        request.requestReceived('GET', '/foo', 'HTTP/1.0')
        data = self.channel.transport.written.getvalue()
        self.assertNotIn("Content-Length", data)
        self.assertIn("Content-Encoding: gzip\r\n", data)
        body = data[data.find("\r\n\r\n") + 4:]
        self.assertEqual("Some data",
                         zlib.decompress(body, 16 + zlib.MAX_WBITS))


    def test_alreadyEncoded(self):
        """
        If the content is already encoded and the I{Content-Encoding} header is
        set, L{server.GzipEncoderFactory} properly appends gzip to it.
        """
        request = server.Request(self.channel, False)
        request.gotLength(0)
        request.requestHeaders.setRawHeaders("Accept-Encoding",
                                             ["deflate", "gzip"])
        request.responseHeaders.setRawHeaders("Content-Encoding",
                                             ["deflate"])
        request.requestReceived('GET', '/foo', 'HTTP/1.0')
        data = self.channel.transport.written.getvalue()
        self.assertNotIn("Content-Length", data)
        self.assertIn("Content-Encoding: deflate,gzip\r\n", data)
        body = data[data.find("\r\n\r\n") + 4:]
        self.assertEqual("Some data",
                         zlib.decompress(body, 16 + zlib.MAX_WBITS))


    def test_multipleEncodingLines(self):
        """
        If there are several I{Content-Encoding} headers,
        L{server.GzipEncoderFactory} normalizes it and appends gzip to the
        field value.
        """
        request = server.Request(self.channel, False)
        request.gotLength(0)
        request.requestHeaders.setRawHeaders("Accept-Encoding",
                                             ["deflate", "gzip"])
        request.responseHeaders.setRawHeaders("Content-Encoding",
                                             ["foo", "bar"])
        request.requestReceived('GET', '/foo', 'HTTP/1.0')
        data = self.channel.transport.written.getvalue()
        self.assertNotIn("Content-Length", data)
        self.assertIn("Content-Encoding: foo,bar,gzip\r\n", data)
        body = data[data.find("\r\n\r\n") + 4:]
        self.assertEqual("Some data",
                         zlib.decompress(body, 16 + zlib.MAX_WBITS))



class RootResource(resource.Resource):
    isLeaf=0
    def getChildWithDefault(self, name, request):
        request.rememberRootURL()
        return resource.Resource.getChildWithDefault(self, name, request)
    def render(self, request):
        return ''

class RememberURLTest(unittest.TestCase):
    def createServer(self, r):
        chan = DummyChannel()
        chan.site = server.Site(r)
        return chan

    def testSimple(self):
        r = resource.Resource()
        r.isLeaf=0
        rr = RootResource()
        r.putChild('foo', rr)
        rr.putChild('', rr)
        rr.putChild('bar', resource.Resource())
        chan = self.createServer(r)
        for url in ['/foo/', '/foo/bar', '/foo/bar/baz', '/foo/bar/']:
            request = server.Request(chan, 1)
            request.setHost('example.com', 81)
            request.gotLength(0)
            request.requestReceived('GET', url, 'HTTP/1.0')
            self.assertEqual(request.getRootURL(), "http://example.com/foo")

    def testRoot(self):
        rr = RootResource()
        rr.putChild('', rr)
        rr.putChild('bar', resource.Resource())
        chan = self.createServer(rr)
        for url in ['/', '/bar', '/bar/baz', '/bar/']:
            request = server.Request(chan, 1)
            request.setHost('example.com', 81)
            request.gotLength(0)
            request.requestReceived('GET', url, 'HTTP/1.0')
            self.assertEqual(request.getRootURL(), "http://example.com/")


class NewRenderResource(resource.Resource):
    def render_GET(self, request):
        return "hi hi"

    def render_HEH(self, request):
        return "ho ho"



class HeadlessResource(object):
    """
    A resource that implements GET but not HEAD.
    """
    implements(resource.IResource)

    allowedMethods = ["GET"]

    def render(self, request):
        """
        Leave the request open for future writes.
        """
        self.request = request
        if request.method not in self.allowedMethods:
            raise error.UnsupportedMethod(self.allowedMethods)
        self.request.write("some data")
        return server.NOT_DONE_YET




class NewRenderTestCase(unittest.TestCase):
    """
    Tests for L{server.Request.render}.
    """
    def _getReq(self, resource=None):
        """
        Create a request object with a stub channel and install the
        passed resource at /newrender. If no resource is passed,
        create one.
        """
        d = DummyChannel()
        if resource is None:
            resource = NewRenderResource()
        d.site.resource.putChild('newrender', resource)
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('example.com', 81)
        request.gotLength(0)
        return request

    def testGoodMethods(self):
        req = self._getReq()
        req.requestReceived('GET', '/newrender', 'HTTP/1.0')
        self.assertEqual(req.transport.getvalue().splitlines()[-1], 'hi hi')

        req = self._getReq()
        req.requestReceived('HEH', '/newrender', 'HTTP/1.0')
        self.assertEqual(req.transport.getvalue().splitlines()[-1], 'ho ho')

    def testBadMethods(self):
        req = self._getReq()
        req.requestReceived('CONNECT', '/newrender', 'HTTP/1.0')
        self.assertEqual(req.code, 501)

        req = self._getReq()
        req.requestReceived('hlalauguG', '/newrender', 'HTTP/1.0')
        self.assertEqual(req.code, 501)

    def testImplicitHead(self):
        req = self._getReq()
        req.requestReceived('HEAD', '/newrender', 'HTTP/1.0')
        self.assertEqual(req.code, 200)
        self.assertEqual(-1, req.transport.getvalue().find('hi hi'))


    def test_unsupportedHead(self):
        """
        HEAD requests against resource that only claim support for GET
        should not include a body in the response.
        """
        resource = HeadlessResource()
        req = self._getReq(resource)
        req.requestReceived("HEAD", "/newrender", "HTTP/1.0")
        headers, body = req.transport.getvalue().split('\r\n\r\n')
        self.assertEqual(req.code, 200)
        self.assertEqual(body, '')



class GettableResource(resource.Resource):
    """
    Used by AllowedMethodsTest to simulate an allowed method.
    """
    def render_GET(self):
        pass

    def render_fred_render_ethel(self):
        """
        The unusual method name is designed to test the culling method
        in C{twisted.web.resource._computeAllowedMethods}.
        """
        pass



class AllowedMethodsTest(unittest.TestCase):
    """
    'C{twisted.web.resource._computeAllowedMethods} is provided by a
    default should the subclass not provide the method.
    """


    def _getReq(self):
        """
        Generate a dummy request for use by C{_computeAllowedMethod} tests.
        """
        d = DummyChannel()
        d.site.resource.putChild('gettableresource', GettableResource())
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('example.com', 81)
        request.gotLength(0)
        return request


    def test_computeAllowedMethods(self):
        """
        C{_computeAllowedMethods} will search through the
        'gettableresource' for all attributes/methods of the form
        'render_{method}' ('render_GET', for example) and return a list of
        the methods. 'HEAD' will always be included from the
        resource.Resource superclass.
        """
        res = GettableResource()
        allowedMethods = resource._computeAllowedMethods(res)
        self.assertEqual(set(allowedMethods),
                          set(['GET', 'HEAD', 'fred_render_ethel']))


    def test_notAllowed(self):
        """
        When an unsupported method is requested, the default
        L{_computeAllowedMethods} method will be called to determine the
        allowed methods, and the HTTP 405 'Method Not Allowed' status will
        be returned with the allowed methods will be returned in the
        'Allow' header.
        """
        req = self._getReq()
        req.requestReceived('POST', '/gettableresource', 'HTTP/1.0')
        self.assertEqual(req.code, 405)
        self.assertEqual(
            set(req.responseHeaders.getRawHeaders('allow')[0].split(", ")),
            set(['GET', 'HEAD','fred_render_ethel'])
        )


    def test_notAllowedQuoting(self):
        """
        When an unsupported method response is generated, an HTML message will
        be displayed.  That message should include a quoted form of the URI and,
        since that value come from a browser and shouldn't necessarily be
        trusted.
        """
        req = self._getReq()
        req.requestReceived('POST', '/gettableresource?'
                            'value=<script>bad', 'HTTP/1.0')
        self.assertEqual(req.code, 405)
        renderedPage = req.transport.getvalue()
        self.assertNotIn("<script>bad", renderedPage)
        self.assertIn('&lt;script&gt;bad', renderedPage)


    def test_notImplementedQuoting(self):
        """
        When an not-implemented method response is generated, an HTML message
        will be displayed.  That message should include a quoted form of the
        requested method, since that value come from a browser and shouldn't
        necessarily be trusted.
        """
        req = self._getReq()
        req.requestReceived('<style>bad', '/gettableresource', 'HTTP/1.0')
        self.assertEqual(req.code, 501)
        renderedPage = req.transport.getvalue()
        self.assertNotIn("<style>bad", renderedPage)
        self.assertIn('&lt;style&gt;bad', renderedPage)



class SDResource(resource.Resource):
    def __init__(self,default):
        self.default = default


    def getChildWithDefault(self, name, request):
        d = defer.succeed(self.default)
        resource = util.DeferredResource(d)
        return resource.getChildWithDefault(name, request)



class DeferredResourceTests(unittest.TestCase):
    """
    Tests for L{DeferredResource}.
    """

    def testDeferredResource(self):
        r = resource.Resource()
        r.isLeaf = 1
        s = SDResource(r)
        d = DummyRequest(['foo', 'bar', 'baz'])
        resource.getChildForRequest(s, d)
        self.assertEqual(d.postpath, ['bar', 'baz'])


    def test_render(self):
        """
        L{DeferredResource} uses the request object's C{render} method to
        render the resource which is the result of the L{Deferred} being
        handled.
        """
        rendered = []
        request = DummyRequest([])
        request.render = rendered.append

        result = resource.Resource()
        deferredResource = util.DeferredResource(defer.succeed(result))
        deferredResource.render(request)
        self.assertEqual(rendered, [result])



class DummyRequestForLogTest(DummyRequest):
    uri = '/dummy' # parent class uri has "http://", which doesn't really happen
    code = 123

    clientproto = 'HTTP/1.0'
    sentLength = None
    client = IPv4Address('TCP', '1.2.3.4', 12345)



class TestLogEscaping(unittest.TestCase):
    def setUp(self):
        self.site = http.HTTPFactory()
        self.site.logFile = StringIO()
        self.request = DummyRequestForLogTest(self.site, False)

    def testSimple(self):
        self.site._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HTTP/1.0" 123 - "-" "-"\n')

    def testMethodQuote(self):
        self.site._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.method = 'G"T'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "G\\"T /dummy HTTP/1.0" 123 - "-" "-"\n')

    def testRequestQuote(self):
        self.site._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.uri='/dummy"withquote'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy\\"withquote HTTP/1.0" 123 - "-" "-"\n')

    def testProtoQuote(self):
        self.site._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.clientproto='HT"P/1.0'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HT\\"P/1.0" 123 - "-" "-"\n')

    def testRefererQuote(self):
        self.site._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.headers['referer'] = 'http://malicious" ".website.invalid'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HTTP/1.0" 123 - "http://malicious\\" \\".website.invalid" "-"\n')

    def testUserAgentQuote(self):
        self.site._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.headers['user-agent'] = 'Malicious Web" Evil'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HTTP/1.0" 123 - "-" "Malicious Web\\" Evil"\n')



class ServerAttributesTestCase(unittest.TestCase):
    """
    Tests that deprecated twisted.web.server attributes raise the appropriate
    deprecation warnings when used.
    """

    def test_deprecatedAttributeDateTimeString(self):
        """
        twisted.web.server.date_time_string should not be used; instead use
        twisted.web.http.datetimeToString directly
        """
        deprecated_func = server.date_time_string
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_deprecatedAttributeDateTimeString])

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            ("twisted.web.server.date_time_string was deprecated in Twisted "
             "12.1.0: Please use twisted.web.http.datetimeToString instead"))


    def test_deprecatedAttributeStringDateTime(self):
        """
        twisted.web.server.string_date_time should not be used; instead use
        twisted.web.http.stringToDatetime directly
        """
        deprecated_func = server.string_date_time
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_deprecatedAttributeStringDateTime])

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            ("twisted.web.server.string_date_time was deprecated in Twisted "
             "12.1.0: Please use twisted.web.http.stringToDatetime instead"))
