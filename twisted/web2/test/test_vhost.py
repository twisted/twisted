from twisted.web2.test.test_server import BaseCase, BaseTestResource
from twisted.web2 import resource
from twisted.web2 import vhost
from twisted.web2 import http, responsecode
from twisted.web2 import iweb
from twisted.web2 import stream
from twisted.web2 import http_headers

class HostResource(BaseTestResource):
    addSlash=True
    def child_bar(self, req):
        return self

    def render(self, req):
        h = req.host
        return http.Response(responsecode.OK, stream=h)

class TestVhost(BaseCase):
    root = vhost.NameVirtualHost(default=HostResource())

    def setUp(self):
        self.root.addHost('foo', HostResource())

    def testNameVirtualHost(self):
        """ Test basic Name Virtual Host behavior
            1) NameVirtualHost.default is defined, so an undefined NVH (localhost)
                gets handled by NameVirtualHost.default

            2) A defined NVH gets passed the proper host header and is handled by the proper resource
        """

        self.assertResponse(
            (self.root, 'http://localhost/'),
            (200, {}, 'localhost'))

        self.assertResponse(
            (self.root, 'http://foo/'),
            (200, {}, 'foo'))

    def testNoDefault(self):
        root = vhost.NameVirtualHost()
        
        # Test lack of host specified
        self.assertResponse(
            (root, 'http://frob/'),
            (404, {}, None))

    def testNameVirtualHostWithChildren(self):
        """ Test that children of a defined NVH are handled appropriately
        """
        
        self.assertResponse(
            (self.root, 'http://foo/bar/'),
            (200, {}, 'foo'))

    def testNameVirtualHostWithNesting(self):
        """ Test that an unknown virtual host gets handled by the domain parent 
            and passed on to the parent's resource.
        """

        nested = vhost.NameVirtualHost()
        nested.addHost('is.nested', HostResource())
        self.root.addHost('nested', nested)

        self.assertResponse(
            (self.root, 'http://is.nested/'),
            (200, {}, 'is.nested'))
    
class PathResource(resource.LeafResource):
    def render(self, req):  
        response = req.scheme+'://'+'/'.join([req.host,] + req.prepath + req.postpath)
        return http.Response(responsecode.OK, stream=response)

class TestURIRewrite(BaseCase):
    def testVHostURIRewrite(self):
        """Test that the hostname, path, and scheme are properly rewritten to defined domain
        """
        vur = vhost.VHostURIRewrite('https://www.apachesucks.org/some/path/', PathResource())
        self.assertResponse(
            (vur, 'http://localhost/'),
            (200, {}, 'https://www.apachesucks.org/some/path/'))

    def testVHostURIRewriteWithChildren(self):
        """ Test that the hostname is properly rewritten and that children are located
        """
        
        vur = vhost.VHostURIRewrite('http://www.apachesucks.org/', 
                HostResource(children=[('foo', PathResource())]))

        self.assertResponse(
            (vur, 'http://localhost/foo'),
            (200, {}, 'http://www.apachesucks.org/foo'))

    def testVHostURIRewriteAsChild(self):
        """ Test that a VHostURIRewrite can exist anywhere in the resource tree
        """

        root = HostResource(children=[('bar', HostResource(children=[ 
                ('vhost.rpy', vhost.VHostURIRewrite('http://www.apachesucks.org/', PathResource()
                                                    ))]))])

        self.assertResponse(
            (root, 'http://localhost/bar/vhost.rpy/foo'),
            (200, {}, 'http://www.apachesucks.org/foo'))

    def testVHostURIRewriteWithSibling(self):
        """ Test that two VHostURIRewrite objects can exist on the same level of the 
            resource tree.
        """
    
        root = HostResource(children=[
                ('vhost1', vhost.VHostURIRewrite('http://foo.bar/', PathResource())), 
                ('vhost2', vhost.VHostURIRewrite('http://baz.bax/', PathResource()))]) 

        self.assertResponse(
            (root, 'http://localhost/vhost1/'),
            (200, {}, 'http://foo.bar/'))

        self.assertResponse(
            (root, 'http://localhost/vhost2/'),
            (200, {}, 'http://baz.bax/'))

def raw(d):
    headers=http_headers.Headers()
    for k,v in d.iteritems():
        headers.setRawHeaders(k, [v])
    return headers

class RemoteAddrResource(resource.LeafResource):
    def render(self, req):
        return http.Response(200, stream=str(req.remoteAddr))

class TestAutoVHostRewrite(BaseCase):
    def setUp(self):
        self.root = vhost.AutoVHostURIRewrite(PathResource())

    def testFullyRewrite(self):
        self.assertResponse(
            (self.root, 'http://localhost/quux', raw({'x-forwarded-host':'foo.bar',
                                              'x-forwarded-for':'1.2.3.4',
                                              'x-app-location':'/baz/',
                                              'x-app-scheme':'https'})),
            (200, {}, 'https://foo.bar/baz/quux'))

    def testRemoteAddr(self):
        self.assertResponse(
            (vhost.AutoVHostURIRewrite(RemoteAddrResource()),
             'http://localhost/', raw({'x-forwarded-host':'foo.bar',
                                       'x-forwarded-for':'1.2.3.4'})),
             (200, {}, "IPv4Address(TCP, '1.2.3.4', 0)"))

    def testSendsRealHost(self):
        self.assertResponse(
            (vhost.AutoVHostURIRewrite(PathResource(), sendsRealHost=True),
             'http://localhost/', raw({'host': 'foo.bar',
                                       'x-forwarded-host': 'baz.bax',
                                       'x-forwarded-for': '1.2.3.4'})),
            (200, {}, 'http://foo.bar/'))

    def testLackingHeaders(self):
        self.assertResponse(
            (self.root, 'http://localhost/', {}),
            (400, {}, None))

    def testMinimalHeaders(self):
        self.assertResponse(
            (self.root, 'http://localhost/', raw({'x-forwarded-host':'foo.bar',
                                              'x-forwarded-for':'1.2.3.4'})),
            (200, {}, 'http://foo.bar/'))
    
    
