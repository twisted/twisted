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
from twisted.web import server, static, client, error, util, resource
from twisted.internet import reactor, defer, interfaces
from twisted.python.util import sibpath
from twisted.python import components

try:
    from twisted.internet import ssl
except:
    ssl = None

import os

serverCallID = None

class LongTimeTakingResource(resource.Resource):
    def render(self, request):
        global serverCallID
        serverCallID =  reactor.callLater(1, self.writeIt, request)
        return server.NOT_DONE_YET

    def writeIt(self, request):
        request.write("hello!!!")
        request.finish()

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

    def render(self, request):
        return request.received_headers["host"]

class PayloadResource(resource.Resource):

    def render(self, request):
        data = request.content.read()
        if len(data) != 100 or int(request.received_headers["content-length"]) != 100:
            return "ERROR"
        return data


class WebClientTestCase(unittest.TestCase):
    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")

    def setUp(self):
        name = str(id(self)) + "_webclient"
        if not os.path.exists(name):
            os.mkdir(name)
            f = open(os.path.join(name, "file"), "wb")
            f.write("0123456789")
            f.close()
        r = static.File(name)
        r.putChild("redirect", util.Redirect("/file"))
        r.putChild("wait", LongTimeTakingResource())
        r.putChild("error", ErrorResource())
        r.putChild("nolength", NoLengthResource())
        r.putChild("host", HostHeaderResource())
        r.putChild("payload", PayloadResource())
        site = server.Site(r, timeout=None)
        self.port = self._listen(site)
        reactor.iterate(); reactor.iterate()
        self.portno = self.port.getHost()[2]

    def tearDown(self):
        if serverCallID and serverCallID.active():
            serverCallID.cancel()
        self.port.stopListening()
        reactor.iterate(); reactor.iterate();
        del self.port

    def getURL(self, path):
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    def testPayload(self):
        s = "0123456789" * 10
        self.assertEquals(unittest.deferredResult(client.getPage(self.getURL("payload"), postdata=s)),
                          s)
        
    def testHostHeader(self):
        # if we pass Host header explicitly, it should be used, otherwise
        # it should extract from url
        self.assertEquals(unittest.deferredResult(client.getPage(self.getURL("host"))),
                          "127.0.0.1")
        self.assertEquals(unittest.deferredResult(client.getPage(self.getURL("host"),
                                                                 headers={"Host": "www.example.com"})),
                          "www.example.com")
    
    def testGetPage(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getURL("file"))),
                          "0123456789")

    def testTimeout(self):
        r = unittest.deferredResult(client.getPage(self.getURL("wait"), timeout=1.5))
        self.assertEquals(r, 'hello!!!')
        f = unittest.deferredError(client.getPage(self.getURL("wait"), timeout=0.5))
        f.trap(defer.TimeoutError)

    def testDownloadPage(self):
        name = self.mktemp()
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name))
        self.assertEquals(open(name, "rb").read(), "0123456789")
        name = self.mktemp()
        r = unittest.deferredResult(client.downloadPage(self.getURL("nolength"), name))
        self.assertEquals(open(name, "rb").read(), "nolength")

    def testDownloadPageError1(self):
        class errorfile:
            def write(self, data):
                raise IOError, "badness happened during write"
            def close(self):
                pass
        ef = errorfile()
        d = client.downloadPage(self.getURL("file"), ef)
        f = unittest.deferredError(d)
        self.failUnless(f.check(IOError))

    def testDownloadPageError2(self):
        class errorfile:
            def write(self, data):
                pass
            def close(self):
                raise IOError, "badness happened during close"
        ef = errorfile()
        d = client.downloadPage(self.getURL("file"), ef)
        f = unittest.deferredError(d)
        self.failUnless(f.check(IOError))

    def testDownloadPageError3(self):
        # make sure failures in open() are caught too. This is tricky.
        # Might only work on posix.
        tmpfile = open("unwritable", "wb")
        tmpfile.close()
        os.chmod("unwritable", 0) # make it unwritable (to us)
        d = client.downloadPage(self.getURL("file"), "unwritable")
        f = unittest.deferredError(d)
        self.failUnless(f.check(IOError))
        os.chmod("unwritable", 0700)
        os.unlink("unwritable")

    def testServerError(self):
        f = unittest.deferredError(client.getPage(self.getURL("nosuchfile")))
        f.trap(error.Error)
        self.assertEquals(f.value.args[0], "404")
        f = unittest.deferredError(client.getPage(self.getURL("error")))
        f.trap(error.Error)
        self.assertEquals(f.value.args[0], "401")
        f = unittest.deferredError(client.getPage(self.getURL("error?showlength=1")))
        f.trap(error.Error)
        self.assertEquals(f.value.args[0], "401")

    def testDownloadServerError(self):
        f = unittest.deferredError(client.downloadPage(self.getURL("nosuchfile"), "nosuchfile"))
        f.trap(error.Error)
        self.assertEquals(f.value.args[0], "404")
        # this is different since content length is 0, and HTTPClient SUCKS
        f = unittest.deferredError(client.downloadPage(self.getURL("error"), "error"))
        f.trap(error.Error)
        self.assertEquals(f.value.args[0], "401")
        f = unittest.deferredError(client.downloadPage(self.getURL("error?showlength=1"), "error"))
        f.trap(error.Error)
        self.assertEquals(f.value.args[0], "401")
        
    def testFactoryInfo(self):
        url = self.getURL('file')
        scheme, host, port, path = client._parse(url)
        factory = client.HTTPClientFactory(url)
        reactor.connectTCP(host, port, factory)
        unittest.deferredResult(factory.deferred)
        self.assertEquals(factory.status, '200')
        self.assert_(factory.version.startswith('HTTP/'))
        self.assertEquals(factory.message, 'OK')
        self.assertEquals(factory.response_headers['content-length'][0], '10')
        

    def testRedirect(self):
        self.assertEquals("0123456789",
            unittest.deferredResult(client.getPage(self.getURL("redirect"))))
        f = unittest.deferredError(client.getPage(self.getURL("redirect"), 
                                                  followRedirect = 0))
        f.trap(error.PageRedirect)
        self.assertEquals(f.value.location, "/file")

    def testPartial(self):
        name = self.mktemp()
        f = open(name, "wb")
        f.write("abcd")
        f.close()
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name,
                                                        supportPartial=1))
        self.assertEquals(open(name, "rb").read(), "abcd456789")
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name,
                                                        supportPartial=1))
        self.assertEquals(open(name, "rb").read(), "abcd456789")
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name))
        self.assertEquals(open(name, "rb").read(), "0123456789")

class WebClientSSLTestCase(WebClientTestCase):
    def _listen(self, site):
        return reactor.listenSSL(0, site,
                                 contextFactory=ssl.DefaultOpenSSLContextFactory(
            sibpath(__file__, 'server.pem'),
            sibpath(__file__, 'server.pem'),
            ),
                                 interface="127.0.0.1")

    def getURL(self, path):
        return "https://127.0.0.1:%d/%s" % (self.portno, path)

    def testFactoryInfo(self):
        url = self.getURL('file')
        scheme, host, port, path = client._parse(url)
        factory = client.HTTPClientFactory(url)
        reactor.connectSSL(host, port, factory, ssl.ClientContextFactory())
        unittest.deferredResult(factory.deferred)
        self.assertEquals(factory.status, '200')
        self.assert_(factory.version.startswith('HTTP/'))
        self.assertEquals(factory.message, 'OK')
        self.assertEquals(factory.response_headers['content-length'][0], '10')

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

        self.tlsPort = reactor.listenSSL(0, tlsSite,
                                         contextFactory=ssl.DefaultOpenSSLContextFactory(
            sibpath(__file__, 'server.pem'),
            sibpath(__file__, 'server.pem'),
            ),
                                         interface="127.0.0.1")
        self.plainPort = reactor.listenTCP(0, plainSite, interface="127.0.0.1")

        reactor.iterate(); reactor.iterate()
        self.plainPortno = self.plainPort.getHost()[2]
        self.tlsPortno = self.tlsPort.getHost()[2]

        plainRoot.putChild('one', util.Redirect(self.getHTTPS('two')))
        tlsRoot.putChild('two', util.Redirect(self.getHTTP('three')))
        plainRoot.putChild('three', util.Redirect(self.getHTTPS('four')))
        tlsRoot.putChild('four', static.Data('FOUND IT!', 'text/plain'))

    def tearDown(self):
        self.plainPort.stopListening()
        self.tlsPort.stopListening()
        reactor.iterate(); reactor.iterate();
        del self.plainPort
        del self.tlsPort

    def testHoppingAround(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getHTTP("one"))),
                          "FOUND IT!")


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
        reactor.iterate(); reactor.iterate()
        self.portno = self.port.getHost()[2]

    def tearDown(self):
        self.port.stopListening()
        reactor.iterate(); reactor.iterate();
        del self.port

    def getHTTP(self, path):
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    def testNoCookies(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getHTTP("cookiemirror"))),
                          "[]")

    def testSomeCookies(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getHTTP("cookiemirror"),
                                                                 cookies={'foo': 'bar',
                                                                          'baz': 'quux'})),
                          "[('baz', 'quux'), ('foo', 'bar')]")

    def testRawNoCookies(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getHTTP("rawcookiemirror"))),
                          "None")

    def testRawSomeCookies(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getHTTP("rawcookiemirror"),
                                                                 cookies={'foo': 'bar',
                                                                          'baz': 'quux'})),
                          "'foo=bar; baz=quux'")

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

if not components.implements(reactor, interfaces.IReactorSSL):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "Reactor doesn't support SSL"

