""" 
    This should more thoroughly test the full API
    instead of just the nevow contributions to it
    but since those are the only bits of the API 
    that I know currently work, It'll have to do.

    This also probably shouldn't depend on nevow.
    But they wrote it ... so oh well :)
"""

from twisted.trial import unittest
from twisted.internet import defer

from twisted.web2 import iweb
from twisted.web2 import server, resource
from twisted.web2.test import util
from zope.interface import implements

class Render(resource.Resource):
    implements(iweb.IResource)
    rendered = False

    def render(self, request):
        self.rendered = True
        return 'Success'


class TestLookup(util.TestCase):
    def getResourceFor(self, root, url):
        r = util.FakeRequest()
        self.request = r
        r.postpath = url.split('/')
        deferred = defer.maybeDeferred(server.Site(root).getResourceFor, r)
        return unittest.deferredResult(
            deferred
        )

    def test_LeafResource(self):
        root = Render()
        foo = resource.LeafResource()
        root.putChild('foo', foo)
        result = self.getResourceFor(root, 'foo/bar/baz')
        self.assertIdentical(result, foo)

    def test_children(self):
        class FirstTwo(Render):
            def locateChild(self, request, segs):
                return LastOne(), segs[2:]

        class LastOne(Render):
            def locateChild(self, request, segs):
                return Render(), segs[1:]

        result = self.getResourceFor(FirstTwo(), 'foo/bar/baz')
        self.assertEquals(result.__class__, Render)

    def test_deferredChild(self):
        class Deferreder(Render):
            def locateChild(self, request, segs):
                d = defer.succeed((self, segs[1:]))
                return d

        r = Deferreder()
        result = self.getResourceFor(r, 'foo')
        self.assertIdentical(r, result)

class TestSiteAndRequest(util.TestCase):
    def renderResource(self, resource, path):
        s = server.Site(resource)
        r = server.Request(util.FakeChannel(s), True)
        D = r.process()
        return unittest.deferredResult(D)

    def test_deferredRender(self):
        class Deferreder(Render):
            def render(self, request):
                return defer.succeed("hello")

        result = self.renderResource(Deferreder(), 'foo')
        self.assertEquals(result, "hello")

    def test_regularRender(self):
        class Regular(Render):
            def render(self, request):
                return "world"

        result = self.renderResource(Regular(), 'bar')
        self.assertEquals(result, 'world')

from twisted.web2 import vhost

class TestVHost(util.TestCase):
    def getResourceFor(self, root, host):
        r = util.FakeRequest()
        self.request = r
        r.setHeader('host', host)
        deferred = defer.maybeDeferred(server.Site(root).getResourceFor, r)
        return unittest.deferredResult(
            deferred
        )

    def test_vhost(self):
        sres1 = Render()
        nvh = vhost.NameVirtualHost()
        nvh.supportNested = False
        nvh.addHost("foo", sres1)
        result = self.getResourceFor(nvh, "foo")
        self.assertEquals(result, sres1)

    def test_vhostNested(self):
        sres1 = Render()
        nvh1 = vhost.NameVirtualHost()
        nvh2 = vhost.NameVirtualHost()
        nvh1.addHost("bar", nvh2)
        nvh2.addHost("foo.bar", sres1)
        result = self.getResourceFor(nvh1, "foo.bar")
        self.assertEquals(result, sres1)

    def getMonsteredRequest(self, root, path):
        r = util.FakeRequest()
        r.postpath = path.split('/')
        deferred = defer.maybeDeferred(server.Site(root).getResourceFor, r)
        return unittest.deferredResult(deferred)
        
       
    # FIXME: 
    #   These should actually compare the request.host and expected host
    #

    def test_vhostMonster(self):
        sres1 = resource.Resource()
        sres1.putChild("vhost.rpy", vhost.VHostMonsterResource())
        result = self.getMonsteredRequest(sres1, "/vhost.rpy/http/example.com:8080/foo/bar")
        self.assertEquals(result, sres1)

    def test_nonRootVHostMonster(self):
        sres1 = Render()
        sres2 = resource.Resource()
        sres2.putChild("vhost.rpy", vhost.VHostMonsterResource())
        sres1.putChild("foo", sres2)
        result = self.getMonsteredRequest(sres1, "/foo/vhost.rpy/http/example.com:8080/foo/bar")
        self.assertEquals(result, sres2, "vhost.VHostMonsterResource() does not support being installed on non-root resources")
        
