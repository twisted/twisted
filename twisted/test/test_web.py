from pyunit import unittest
import string, random, copy

from twisted.web import server, resource, widgets, guard
from twisted.python import defer
from twisted.internet import app
from twisted.cred import service, identity, perspective
from twisted.protocols import http, loopback

class DateTimeTest(unittest.TestCase):
    """Test date parsing functions."""
    def testRoundtrip(self):
        for i in range(10000):
            time = random.randint(0, 2000000000)
            timestr = server.date_time_string(time)
            time2 = server.string_date_time(timestr)
            self.assertEquals(time, time2)


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

class ArgProcessingResource(resource.Resource):
    def processArgs(self, request):
        args = copy.copy(request.args)
        args.update({"bleh": "foo"})
        return args

    def render(self, request):
        return "args: " + str(request.args)


class TestHTTPClient(http.HTTPClient):
    
    expected_result = "args: {'bleh': 'foo'}"
    
    def connectionMade(self):
        self.sendCommand("GET", "/")
        self.endHeaders()

    def handleStatus(self, version, status, message):
        pass
    
    def handleResponse(self, data):
        if data != self.expected_result:
            print "-- EXPECTED --"
            print self.expected_result
            print "-- RECEIVED --"
            print data
            raise ValueError("data != %s. see STDOUT." % self.expected_result)

    def handleHeader(self, key, value):
        pass

    def handleEndHeaders(self):
        pass


class LoopbackSite(loopback.LoopbackRelay, server.Site):
    def __init__(self, resource, client):
        loopback.LoopbackRelay.__init__(self, client)
        server.Site.__init__(self, resource)

    def stopConsuming(self):
        self.loseConnection()


class LoopbackSiteTestCase(unittest.TestCase):

    def testArgProcessingResource(self):
        res = resource.Resource()
        argRes = ArgProcessingResource()
        res.putChild("", argRes)
        client = TestHTTPClient()
        serverToClient = LoopbackSite(res, client)
        req = serverToClient.buildProtocol("addr")
        clientToServer = loopback.LoopbackRelay(req)
        req.makeConnection(serverToClient)
        client.makeConnection(clientToServer)
        while 1:
            serverToClient.clearBuffer()
            clientToServer.clearBuffer()
            if serverToClient.shouldLose or clientToServer.shouldLose:
                break


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
        self.app = app.Application("guard")
        ident = identity.Identity("bob", self.app)
        ident.setPassword("joe")
        self.app.authorizer.addIdentity(ident)
        self.svc = service.Service("simple", self.app)
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
        d.addArg('__formtype__', str(guard.AuthForm))
        g.render(d)
        assert d.finished, "didn't finish"
        w = string.join(d.written,'%%%%')
        # print w
        assert d.written == ['correct'], "incorrect result: %s"% w

testCases = [DateTimeTest, SiteTest, WidgetTest, GuardTest]
