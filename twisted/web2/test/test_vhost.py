from twisted.web2.test.test_server import BaseCase, BaseTestResource
from twisted.web2 import resource
from twisted.web2 import vhost
from twisted.web2 import http, responsecode
from twisted.web2 import iweb
from twisted.web2 import stream

class HostResource(BaseTestResource):
    def child_bar(self, ctx):
        return self

    def render(self, ctx):
        h = iweb.IRequest(ctx).host
        return http.Response(responsecode.OK, stream=stream.MemoryStream(h))

class PathResource(BaseTestResource):
    def render(self, ctx):  
        r = iweb.IRequest(ctx)
        response = '/'.join([r.host,] + r.prepath)
        return http.Response(responsecode.OK, stream=stream.MemoryStream(response))

class TestVhost(BaseCase):
    root = vhost.NameVirtualHost(default=HostResource())

    def setUp(self):
        self.root.addHost('foo', HostResource())

    def testNameVirtualHost(self):
        self.assertResponse(
            (self.root, 'http://localhost/'),
            (200, {}, 'localhost'))

        self.assertResponse(
            (self.root, 'http://foo/'),
            (200, {}, 'foo'))

    def testNameVirtualHostWithChildren(self):
        self.assertResponse(
            (self.root, 'http://foo/bar'),
            (200, {}, 'foo'))

    def testNameVirtualHostWithNesting(self):
        nested = vhost.NameVirtualHost()
        nested.addHost('is.nested', HostResource())
        self.root.addHost('nested', nested)

        self.assertResponse(
            (self.root, 'http://is.nested/'),
            (200, {}, 'is.nested'))
    
    def testVHostURIRewrite(self):
        vur = vhost.VHostURIRewrite('http://www.apachesucks.org/', HostResource())
        self.assertResponse(
            (vur, 'http://localhost/'),
            (200, {}, 'www.apachesucks.org'))

    def testVHostURIRewriteWithChildren(self):
        vur = vhost.VHostURIRewrite('http://www.apachesucks.org/', 
                HostResource(children=[('foo', PathResource())]))

        self.assertResponse(
            (vur, 'http://localhost/foo'),
            (200, {}, 'www.apachesucks.org/foo'))

    def testVHostURIRewriteAsChild(self):
        root = HostResource(children=[('bar', HostResource(children=[ 
                ('vhost.rpy', vhost.VHostURIRewrite('http://www.apachesucks.org/', HostResource(
                    children=[('foo', PathResource())])))]))])

        self.assertResponse(
            (root, 'http://localhost/bar/vhost.rpy/foo'),
            (200, {}, 'www.apachesucks.org/bar/foo'))

