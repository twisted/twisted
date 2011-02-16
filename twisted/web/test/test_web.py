# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for various parts of L{twisted.web}.
"""

from cStringIO import StringIO

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.internet import reactor
from twisted.internet.address import IPv4Address
from twisted.internet.defer import Deferred
from twisted.web import server, resource, util
from twisted.internet import defer, interfaces, task
from twisted.web import iweb, http, http_headers
from twisted.python import log


class DummyRequest:
    """
    Represents a dummy or fake request.

    @ivar _finishedDeferreds: C{None} or a C{list} of L{Deferreds} which will
        be called back with C{None} when C{finish} is called or which will be
        errbacked if C{processingFailed} is called.

    @type headers: C{dict}
    @ivar headers: A mapping of header name to header value for all request
        headers.

    @type outgoingHeaders: C{dict}
    @ivar outgoingHeaders: A mapping of header name to header value for all
        response headers.

    @type responseCode: C{int}
    @ivar responseCode: The response code which was passed to
        C{setResponseCode}.

    @type written: C{list} of C{str}
    @ivar written: The bytes which have been written to the request.
    """
    uri = 'http://dummy/'
    method = 'GET'
    client = None

    def registerProducer(self, prod,s):
        self.go = 1
        while self.go:
            prod.resumeProducing()

    def unregisterProducer(self):
        self.go = 0


    def __init__(self, postpath, session=None):
        self.sitepath = []
        self.written = []
        self.finished = 0
        self.postpath = postpath
        self.prepath = []
        self.session = None
        self.protoSession = session or server.Session(0, self)
        self.args = {}
        self.outgoingHeaders = {}
        self.responseHeaders = http_headers.Headers()
        self.responseCode = None
        self.headers = {}
        self._finishedDeferreds = []


    def getHeader(self, name):
        """
        Retrieve the value of a request header.

        @type name: C{str}
        @param name: The name of the request header for which to retrieve the
            value.  Header names are compared case-insensitively.

        @rtype: C{str} or L{NoneType}
        @return: The value of the specified request header.
        """
        return self.headers.get(name.lower(), None)


    def setHeader(self, name, value):
        """TODO: make this assert on write() if the header is content-length
        """
        self.outgoingHeaders[name.lower()] = value

    def getSession(self):
        if self.session:
            return self.session
        assert not self.written, "Session cannot be requested after data has been written."
        self.session = self.protoSession
        return self.session


    def render(self, resource):
        """
        Render the given resource as a response to this request.

        This implementation only handles a few of the most common behaviors of
        resources.  It can handle a render method that returns a string or
        C{NOT_DONE_YET}.  It doesn't know anything about the semantics of
        request methods (eg HEAD) nor how to set any particular headers.
        Basically, it's largely broken, but sufficient for some tests at least.
        It should B{not} be expanded to do all the same stuff L{Request} does.
        Instead, L{DummyRequest} should be phased out and L{Request} (or some
        other real code factored in a different way) used.
        """
        result = resource.render(self)
        if result is server.NOT_DONE_YET:
            return
        self.write(result)
        self.finish()


    def write(self, data):
        self.written.append(data)

    def notifyFinish(self):
        """
        Return a L{Deferred} which is called back with C{None} when the request
        is finished.  This will probably only work if you haven't called
        C{finish} yet.
        """
        finished = Deferred()
        self._finishedDeferreds.append(finished)
        return finished


    def finish(self):
        """
        Record that the request is finished and callback and L{Deferred}s
        waiting for notification of this.
        """
        self.finished = self.finished + 1
        if self._finishedDeferreds is not None:
            observers = self._finishedDeferreds
            self._finishedDeferreds = None
            for obs in observers:
                obs.callback(None)


    def processingFailed(self, reason):
        """
        Errback and L{Deferreds} waiting for finish notification.
        """
        if self._finishedDeferreds is not None:
            observers = self._finishedDeferreds
            self._finishedDeferreds = None
            for obs in observers:
                obs.errback(reason)


    def addArg(self, name, value):
        self.args[name] = [value]


    def setResponseCode(self, code, message=None):
        """
        Set the HTTP status response code, but takes care that this is called
        before any data is written.
        """
        assert not self.written, "Response code cannot be set after data has been written: %s." % "@@@@".join(self.written)
        self.responseCode = code
        self.responseMessage = message


    def setLastModified(self, when):
        assert not self.written, "Last-Modified cannot be set after data has been written: %s." % "@@@@".join(self.written)


    def setETag(self, tag):
        assert not self.written, "ETag cannot be set after data has been written: %s." % "@@@@".join(self.written)


    def getClientIP(self):
        """
        Return the IPv4 address of the client which made this request, if there
        is one, otherwise C{None}.
        """
        if isinstance(self.client, IPv4Address):
            return self.client.host
        return None


class ResourceTestCase(unittest.TestCase):
    def testListEntities(self):
        r = resource.Resource()
        self.failUnlessEqual([], r.listEntities())


class SimpleResource(resource.Resource):
    def render(self, request):
        if http.CACHED in (request.setLastModified(10),
                           request.setETag('MatchingTag')):
            return ''
        else:
            return "correct"


class DummyChannel:
    class TCP:
        port = 80
        disconnected = False

        def __init__(self):
            self.written = StringIO()
            self.producers = []

        def getPeer(self):
            return IPv4Address("TCP", '192.168.1.1', 12344)

        def write(self, bytes):
            assert isinstance(bytes, str)
            self.written.write(bytes)

        def writeSequence(self, iovec):
            map(self.write, iovec)

        def getHost(self):
            return IPv4Address("TCP", '10.0.0.1', self.port)

        def registerProducer(self, producer, streaming):
            self.producers.append((producer, streaming))

        def loseConnection(self):
            self.disconnected = True


    class SSL(TCP):
        implements(interfaces.ISSLTransport)

    site = server.Site(resource.Resource())

    def __init__(self):
        self.transport = self.TCP()


    def requestDone(self, request):
        pass



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

    # XXX: test web.distrib.

    def setUp(self):
        self.resrc = SimpleResource()
        self.resrc.putChild('', self.resrc)
        self.site = server.Site(self.resrc)
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
        for l in ["GET / HTTP/1.1",
                  "Accept: text/html"]:
            self.channel.lineReceived(l)

    def tearDown(self):
        self.channel.connectionLost(None)


    def _modifiedTest(self, modifiedSince):
        """
        Given the value C{modifiedSince} for the I{If-Modified-Since}
        header, verify that a response with a 200 code and the resource as
        the body is returned.
        """
        self.channel.lineReceived("If-Modified-Since: " + modifiedSince)
        self.channel.lineReceived('')
        result = self.transport.getvalue()
        self.failUnlessEqual(httpCode(result), http.OK)
        self.failUnlessEqual(httpBody(result), "correct")


    def test_modified(self):
        """
        If a request is made with an I{If-Modified-Since} header value with
        a timestamp indicating a time before the last modification of the
        requested resource, a 200 response is returned along with a response
        body containing the resource.
        """
        self._modifiedTest(http.datetimeToString(1))


    def test_unmodified(self):
        """
        If a request is made with an I{If-Modified-Since} header value with
        a timestamp indicating a time after the last modification of the
        request resource, a 304 response is returned along with an empty
        response body.
        """
        self.channel.lineReceived("If-Modified-Since: %s"
                                  % http.datetimeToString(100))
        self.channel.lineReceived('')
        result = self.transport.getvalue()
        self.failUnlessEqual(httpCode(result), http.NOT_MODIFIED)
        self.failUnlessEqual(httpBody(result), "")


    def test_invalidTimestamp(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        cannot be parsed, the header is treated as not having been present
        and a normal 200 response is returned with a response body
        containing the resource.
        """
        self._modifiedTest("like, maybe a week ago, I guess?")


    def test_invalidTimestampYear(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        contains a string in the year position which is not an integer, the
        header is treated as not having been present and a normal 200
        response is returned with a response body containing the resource.
        """
        self._modifiedTest("Thu, 01 Jan blah 00:00:10 GMT")


    def test_invalidTimestampTooLongAgo(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        contains a year before the epoch, the header is treated as not
        having been present and a normal 200 response is returned with a
        response body containing the resource.
        """
        self._modifiedTest("Thu, 01 Jan 1899 00:00:10 GMT")


    def test_invalidTimestampMonth(self):
        """
        If a request is made with an I{If-Modified-Since} header value which
        contains a string in the month position which is not a recognized
        month abbreviation, the header is treated as not having been present
        and a normal 200 response is returned with a response body
        containing the resource.
        """
        self._modifiedTest("Thu, 01 Blah 1970 00:00:10 GMT")


    def test_etagMatchedNot(self):
        """If-None-Match ETag cache validator (positive)"""
        self.channel.lineReceived("If-None-Match: unmatchedTag")
        self.channel.lineReceived('')
        result = self.transport.getvalue()
        self.failUnlessEqual(httpCode(result), http.OK)
        self.failUnlessEqual(httpBody(result), "correct")

    def test_etagMatched(self):
        """If-None-Match ETag cache validator (negative)"""
        self.channel.lineReceived("If-None-Match: MatchingTag")
        self.channel.lineReceived('')
        result = self.transport.getvalue()
        self.failUnlessEqual(httpHeader(result, "ETag"), "MatchingTag")
        self.failUnlessEqual(httpCode(result), http.NOT_MODIFIED)
        self.failUnlessEqual(httpBody(result), "")



from twisted.web import google
class GoogleTestCase(unittest.TestCase):
    def testCheckGoogle(self):
        raise unittest.SkipTest("no violation of google ToS")
        d = google.checkGoogle('site:www.twistedmatrix.com twisted')
        d.addCallback(self.assertEquals, 'http://twistedmatrix.com/')
        return d





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


class NewRenderTestCase(unittest.TestCase):
    def _getReq(self):
        d = DummyChannel()
        d.site.resource.putChild('newrender', NewRenderResource())
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('example.com', 81)
        request.gotLength(0)
        return request

    def testGoodMethods(self):
        req = self._getReq()
        req.requestReceived('GET', '/newrender', 'HTTP/1.0')
        self.assertEquals(req.transport.getvalue().splitlines()[-1], 'hi hi')

        req = self._getReq()
        req.requestReceived('HEH', '/newrender', 'HTTP/1.0')
        self.assertEquals(req.transport.getvalue().splitlines()[-1], 'ho ho')

    def testBadMethods(self):
        req = self._getReq()
        req.requestReceived('CONNECT', '/newrender', 'HTTP/1.0')
        self.assertEquals(req.code, 501)

        req = self._getReq()
        req.requestReceived('hlalauguG', '/newrender', 'HTTP/1.0')
        self.assertEquals(req.code, 501)

    def testImplicitHead(self):
        req = self._getReq()
        req.requestReceived('HEAD', '/newrender', 'HTTP/1.0')
        self.assertEquals(req.code, 200)
        self.assertEquals(-1, req.transport.getvalue().find('hi hi'))



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
        self.assertEquals(rendered, [result])



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
        http._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HTTP/1.0" 123 - "-" "-"\n')

    def testMethodQuote(self):
        http._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.method = 'G"T'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "G\\"T /dummy HTTP/1.0" 123 - "-" "-"\n')

    def testRequestQuote(self):
        http._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.uri='/dummy"withquote'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy\\"withquote HTTP/1.0" 123 - "-" "-"\n')

    def testProtoQuote(self):
        http._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.clientproto='HT"P/1.0'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HT\\"P/1.0" 123 - "-" "-"\n')

    def testRefererQuote(self):
        http._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.headers['referer'] = 'http://malicious" ".website.invalid'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HTTP/1.0" 123 - "http://malicious\\" \\".website.invalid" "-"\n')

    def testUserAgentQuote(self):
        http._logDateTime = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
            25, 'Oct', 2004, 12, 31, 59)
        self.request.headers['user-agent'] = 'Malicious Web" Evil'
        self.site.log(self.request)
        self.site.logFile.seek(0)
        self.assertEqual(
            self.site.logFile.read(),
            '1.2.3.4 - - [25/Oct/2004:12:31:59 +0000] "GET /dummy HTTP/1.0" 123 - "-" "Malicious Web\\" Evil"\n')
