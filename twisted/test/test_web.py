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

from twisted.web import server, resource, widgets, guard
from twisted.internet import app, defer
from twisted.cred import service, identity, perspective, authorizer
from twisted.protocols import http, loopback
from twisted.python import log, reflect

class DummyRequest:
    uri='http://dummy/'
    def __init__(self, postpath, session=None):
        self.sitepath = []
        self.written = []
        self.finished = 0
        self.postpath = postpath
        self.prepath = []
        self.session = None
        self.protoSession = session or server.Session(0, self)
        self.args = {}
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

class SimpleWidget(widgets.Widget):
    def display(self, request):
        return ['correct']

class TextDeferred(widgets.Widget):
    def __init__(self, text):
        self.text = text

    def display(self, request):
        d = defer.Deferred()
        d.callback([self.text])
        return [d]


class DeferredWidget(widgets.Widget):
    def display(self, request):
        d = defer.Deferred()
        d.callback(["correct"])
        return [d]

class MultiDeferredWidget(widgets.Widget):
    def display(self, request):
        d = defer.Deferred()
        d2 = defer.Deferred()
        d3 = defer.Deferred()
        d.callback([d2])
        d2.callback([d3])
        d3.callback(["correct"])
        return [d]

class WidgetTest(unittest.TestCase):
    def testSimpleRenderSession(self):
        w1 = SimpleWidget()
        d = DummyRequest([''])
        widgets.WidgetResource(w1).render(d)
        assert d.finished
        assert d.written == ['correct']

    def testDeferredRenderSession(self):
        w1 = DeferredWidget()
        d = DummyRequest([''])
        widgets.WidgetResource(w1).render(d)
        assert d.finished
        assert d.written == ['correct']

    def testMultiDeferredRenderSession(self):
        w1 = MultiDeferredWidget()
        d = DummyRequest([''])
        widgets.WidgetResource(w1).render(d)
        assert d.finished
        assert d.written == ['correct']

class GuardTest(unittest.TestCase):
    def setUp(self):
        self.auth = authorizer.DefaultAuthorizer()
        self.app = app.Application("guard", authorizer=self.auth)
        ident = identity.Identity("bob", authorizer=self.auth)
        ident.setPassword("joe")
        self.auth.addIdentity(ident)
        self.svc = service.Service("simple", authorizer=self.auth, serviceParent=self.app)
        self.psp = perspective.Perspective('jethro',ident.name)
        self.svc.addPerspective(self.psp)
        ident.addKeyForPerspective(self.psp)

    def testSuccess(self):
        g = guard.ResourceGuard(SimpleResource(), self.svc)
        d = DummyRequest([])
        g.render(d)
        assert d.written != ['correct']
        assert d.finished
        d = DummyRequest([])
        d.site = self
        d.addArg('username', 'bob')
        d.addArg('password', 'joe')
        d.addArg('perspective', 'jethro')
        d.addArg('__formtype__', reflect.qual(guard.AuthForm))
        g.render(d)
        assert d.finished, "didn't finish"
        assert d.written == ['correct'], "incorrect result: %s" % d.written


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
