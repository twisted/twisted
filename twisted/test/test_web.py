from pyunit import unittest
import string

from twisted.web import server, resource, widgets, guard
from twisted.python import defer
from twisted.internet import main, passport


class DummyRequest:
    def __init__(self, postpath, session=None):
        self.written = []
        self.finished = 0
        self.postpath = postpath
        self.prepath = []
        self.session = None
        self.protoSession = session or server.Session(0)
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

class SimpleResource(resource.Resource):
    def render(self, request):
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
        self.app = main.Application("guard")
        ident = passport.Identity("bob", self.app)
        ident.setPassword("joe")
        self.app.authorizer.addIdentity(ident)
        self.svc = passport.Service("simple", self.app)
        self.psp = passport.Perspective('jethro',ident.name)
        self.svc.addPerspective(self.psp)
        ident.addKeyForPerspective(self.psp)

    def testSuccess(self):
        g = guard.ResourceGuard(SimpleResource(), "simple")
        d = DummyRequest([])
        # It will look for the 'app' attribute...
        d.site = self
        g.render(d)
        assert d.written != ['correct']
        assert d.finished
        d = DummyRequest([])
        d.site = self
        d.addArg('username', 'bob')
        d.addArg('password', 'joe')
        d.addArg('perspective', 'jethro')
        d.addArg('__formtype__', str(guard.AuthForm))
        g.render(d)
        assert d.finished, "didn't finish"
        w = string.join(d.written,'%%%%')
        print w
        assert d.written == ['correct'], "incorrect result: %s"% w

testCases = [SiteTest, WidgetTest, GuardTest]
