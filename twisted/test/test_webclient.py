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
from twisted.internet import reactor, defer
from twisted.python.util import sibpath

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

    def testError(self):
        f = unittest.deferredError(client.getPage(self.getURL("nosuchfile")))
        f.trap(error.Error)

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
        self.assertEquals(unittest.deferredResult(client.getPage(self.getURL("redirect"))),
                          "0123456789")

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

if ssl is None or not hasattr(ssl, 'DefaultOpenSSLContextFactory'):
    for case in [WebClientSSLTestCase, WebClientRedirectBetweenSSLandPlainText]:
        case.skip = "OpenSSL not present"
