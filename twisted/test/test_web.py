# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
from twisted.trial import unittest
import string, random, copy

from twisted.web import server, resource, util
from twisted.internet import defer, interfaces
from twisted.protocols import http, loopback
from twisted.python import log, reflect
from twisted.internet.address import IPv4Address

class DummyRequest:
    uri='http://dummy/'
    method = 'GET'

    def getHeader(self, h):
        return None

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
    def write(self, data):
        self.written.append(data)
    def finish(self):
        self.finished = self.finished + 1
    def addArg(self, name, value):
        self.args[name] = [value]
    def setResponseCode(self, code):
        assert not self.written, "Response code cannot be set after data has been written: %s." % string.join(self.written, "@@@@")
    def setLastModified(self, when):
        assert not self.written, "Last-Modified cannot be set after data has been written: %s." % string.join(self.written, "@@@@")
    def setETag(self, tag):
        assert not self.written, "ETag cannot be set after data has been written: %s." % string.join(self.written, "@@@@")

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

class SiteTest(unittest.TestCase):
    def testSimplestSite(self):
        sres1 = SimpleResource()
        sres2 = SimpleResource()
        sres1.putChild("",sres2)
        site = server.Site(sres1)
        assert site.getResourceFor(DummyRequest([''])) is sres2, "Got the wrong resource."


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
    """web.server's handling of conditional requests for cache validation."""

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

    def test_modified(self):
        """If-Modified-Since cache validator (positive)"""
        self.channel.lineReceived("If-Modified-Since: %s"
                                  % http.datetimeToString(1))
        self.channel.lineReceived('')
        result = self.transport.getvalue()
        self.failUnlessEqual(httpCode(result), http.OK)
        self.failUnlessEqual(httpBody(result), "correct")

    def test_unmodified(self):
        """If-Modified-Since cache validator (negative)"""
        self.channel.lineReceived("If-Modified-Since: %s"
                                  % http.datetimeToString(100))
        self.channel.lineReceived('')
        result = self.transport.getvalue()
        self.failUnlessEqual(httpCode(result), http.NOT_MODIFIED)
        self.failUnlessEqual(httpBody(result), "")

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
        r = unittest.deferredResult(d)
        self.assertEquals(r, 'http://twistedmatrix.com/')

from twisted.web import static
from twisted.web import script

class StaticFileTest(unittest.TestCase):

    def testStaticPaths(self):
        import os
        dp = os.path.join(self.mktemp(),"hello")
        ddp = os.path.join(dp, "goodbye")
        tp = os.path.abspath(os.path.join(dp,"world.txt"))
        tpy = os.path.join(dp,"wyrld.rpy")
        os.makedirs(dp)
        f = open(tp,"wb")
        f.write("hello world")
        f = open(tpy, "wb")
        f.write("""
from twisted.web.static import Data
resource = Data('dynamic world','text/plain')
""")
        f = static.File(dp)
        f.processors = {
            '.rpy': script.ResourceScript,
            }

        f.indexNames = f.indexNames + ['world.txt']
        self.assertEquals(f.getChild('', DummyRequest([''])).path,
                          tp)
        self.assertEquals(f.getChild('wyrld.rpy', DummyRequest(['wyrld.rpy'])
                                     ).__class__,
                          static.Data)
        f = static.File(dp)
        wtextr = DummyRequest(['world.txt'])
        wtext = f.getChild('world.txt', wtextr)
        self.assertEquals(wtext.path, tp)
        wtext.render(wtextr)
        self.assertEquals(wtextr.outgoingHeaders.get('content-length'),
                          str(len('hello world')))
        self.assertNotEquals(f.getChild('', DummyRequest([''])).__class__,
                             static.File)

    def testIgnoreExt(self):
        f = static.File(".")
        f.ignoreExt(".foo")
        self.assertEquals(f.ignoredExts, [".foo"])
        f = static.File(".")
        self.assertEquals(f.ignoredExts, [])
        f = static.File(".", ignoredExts=(".bar", ".baz"))
        self.assertEquals(f.ignoredExts, [".bar", ".baz"])

    def testIgnoredExts(self):
        import os
        dp = os.path.join(self.mktemp(), 'allYourBase')
        fp = os.path.join(dp, 'AreBelong.ToUs')
        os.makedirs(dp)
        open(fp, 'wb').write("Take off every 'Zig'!!")
        f = static.File(dp)
        f.ignoreExt('.ToUs')
        dreq = DummyRequest([''])
        child_without_ext = f.getChild('AreBelong', dreq)
        self.assertNotEquals(child_without_ext, f.childNotFound)

class DummyChannel:
    class Baz:
        port = 80
        def getPeer(self):
            return IPv4Address("TCP", 'client.example.com', 12344)
        def getHost(self):
            return IPv4Address("TCP", 'example.com', self.port)
    class SSLBaz(Baz):
        __implements__ = interfaces.ISSLTransport,
    transport = Baz()
    site = server.Site(resource.Resource())

class TestRequest(unittest.TestCase):

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
        d.transport = DummyChannel.Baz()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('example.com', 81)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'http://example.com:81/foo/bar')

    def testPrePathURLSSLPort(self):
        d = DummyChannel()
        d.transport = DummyChannel.Baz()
        d.transport.port = 443
        request = server.Request(d, 1)
        request.setHost('example.com', 443)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'http://example.com:443/foo/bar')

    def testPrePathURLSSLPortAndSSL(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSLBaz()
        d.transport.port = 443
        request = server.Request(d, 1)
        request.setHost('example.com', 443)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://example.com/foo/bar')

    def testPrePathURLHTTPPortAndSSL(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSLBaz()
        d.transport.port = 80
        request = server.Request(d, 1)
        request.setHost('example.com', 80)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://example.com:80/foo/bar')

    def testPrePathURLSSLNonDefault(self):
        d = DummyChannel()
        d.transport = DummyChannel.SSLBaz()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('example.com', 81)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://example.com:81/foo/bar')

    def testPrePathURLSetSSLHost(self):
        d = DummyChannel()
        d.transport = DummyChannel.Baz()
        d.transport.port = 81
        request = server.Request(d, 1)
        request.setHost('foo.com', 81, 1)
        request.gotLength(0)
        request.requestReceived('GET', '/foo/bar', 'HTTP/1.0')
        self.assertEqual(request.prePathURL(), 'https://foo.com:81/foo/bar')
        
class RootResource(resource.Resource):
    isLeaf=0
    def getChildWithDefault(self, name, request):
        request.rememberRootURL()
        return resource.Resource.getChildWithDefault(self, name, request)
    def render(self, request):
        return ''

class RememberURLTest(unittest.TestCase):

    def setUp(self):
        d = DummyChannel()
        d.transport = DummyChannel.Baz()
        r = resource.Resource()
        r.isLeaf=0
        rr = RootResource()
        r.putChild('foo', rr)
        rr.putChild('', rr)
        rr.putChild('bar', resource.Resource())
        d.site = server.Site(r)
        self.d = d

    def testSimple(self):
        for url in ['/foo/', '/foo/bar', '/foo/bar/baz', 'foo/bar/']:
            request = server.Request(self.d, 1)
            request.setHost('example.com', 81)
            request.gotLength(0)
            request.requestReceived('GET', '/foo/bar/baz', 'HTTP/1.0')
            self.assertEqual(request.getRootURL(), "http://example.com/foo")


class NewRenderResource(resource.Resource):
    def render_GET(self, request):
        return "hi hi"

    def render_HEH(self, request):
        return "ho ho"


class NewRenderTestCase(unittest.TestCase):
    def _getReq(self):
        d = DummyChannel()
        d.site.resource.putChild('newrender', NewRenderResource())
        d.transport = DummyChannel.Baz()
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
    def __init__(self,default):  self.default=default
    def getChildWithDefault(self,name,request):
        d=defer.succeed(self.default)
        return util.DeferredResource(d).getChildWithDefault(name, request)

class SDTest(unittest.TestCase):

    def testDeferredResource(self):
        r = resource.Resource()
        r.isLeaf = 1
        s = SDResource(r)
        d = DummyRequest(['foo', 'bar', 'baz'])
        resource.getChildForRequest(s, d)
        self.assertEqual(d.postpath, ['bar', 'baz'])
