"""
A test harness for the twisted.web2 server.
"""

from zope.interface import implements
from twisted.web2 import http, http_headers, iweb, server
from twisted.web2 import resource, responsecode, stream
from twisted.trial import unittest, util, assertions
from twisted.internet import defer

class TestChanRequest:
    implements(iweb.IChanRequest)

    def __init__(self, site, method, prepath, uri,
                 headers=None, version=(1,1)):
        self.site = site
        self.method = method
        self.prepath = prepath
        self.uri = uri
        if headers is None:
            headers = http_headers.Headers()
        self.headers = headers
        self.http_version = version
        # Anything below here we do not pass as arguments
        self.request = server.Request(self,
                                      self.method,
                                      self.uri,
                                      self.http_version,
                                      self.headers,
                                      site=self.site,
                                      prepathuri=self.prepath)
        self.code = None
        self.responseHeaders = None
        self.data = ''
        self.deferredFinish = defer.Deferred()

    def writeIntermediateResponse(code, headers=None):
        pass
    
    def writeHeaders(self, code, headers):
        self.responseHeaders = headers
        self.code = code
        
    def write(self, data):
        self.data += data

    def finish(self):
        result = self.code, self.responseHeaders, self.data
        self.finished = True
        self.deferredFinish.callback(result)

    def abortConnection(self):
        pass

    def registerProducer(self, producer, streaming):
        pass

    def unregisterProducer(self):
        pass


class BaseTestResource(resource.Resource):
    responseCode = 200
    responseText = 'This is a fake resource.'
    addSlash = False

    def __init__(self, children=[]):
        """
        @type children: C{list} of C{tuple}
        @param children: a list of ('path', resource) tuples
        """
        for i in children:
            self.putChild(i[0], i[1])

    def render(self, ctx):
        return http.Response(self.responseCode, stream=self.responseStream())

    def responseStream(self):
        return stream.MemoryStream(self.responseText)


class BaseCase(unittest.TestCase):
    """
    Base class for test cases that involve testing the result
    of arbitrary HTTP(S) queries.
    """
    
    method = 'GET'
    version = (1, 1)
    wait_timeout = 5.0
    
    def chanrequest(self, root, uri, headers, method, version, prepath):
        site = server.Site(root)
        return TestChanRequest(site, method, prepath, uri, headers, version)

    def getResponseFor(self, root, uri, headers={},
                       method=None, version=None, prepath=''):
        headers = http_headers.Headers(headers)
        if not headers.hasHeader('content-length'):
            headers.setHeader('content-length', 0)
        if method is None:
            method = self.method
        if version is None:
            version = self.version
        cr = self.chanrequest(root, uri, headers, method, version, prepath)
        cr.request.process()
        return cr.deferredFinish

    def assertResponse(self, request_data, expected_response):
        """
        @type request_data: C{tuple}
        @type expected_response: C{tuple}
        @param request_data: A tuple of arguments to pass to L{getResponseFor}:
                             (root, uri, headers, method, version, prepath).
                             Root resource and requested URI are required,
                             and everything else is optional.
        @param expected_response: A 3-tuple of the expected response:
                                  (responseCode, headers, htmlData)
        """
        d = self.getResponseFor(*request_data)
        d.addCallback(self._cbGotResponse, expected_response)
        util.wait(d, timeout=self.wait_timeout)

    def _cbGotResponse(self, (code, headers, data), expected_response):
        expected_code, expected_headers, expected_data = expected_response
        self.assertEquals(code, expected_code)
        if expected_data is not None:
            self.assertEquals(data, expected_data)
        for key, value in expected_headers.iteritems():
            self.assertEquals(headers.getHeader(key), value)


class SampleWebTest(BaseCase):
    class SampleTestResource(BaseTestResource):
        addSlash = True
        def child_validChild(self, ctx):
            f = BaseTestResource()
            f.responseCode = 200
            f.responseText = 'This is a valid child resource.'
            return f

        def child_missingChild(self, ctx):
            f = BaseTestResource()
            f.responseCode = 404
            f.responseStream = lambda self: None
            return f

    def setUp(self):
        self.root = self.SampleTestResource()

    def test_root(self):
        self.assertResponse(
            (self.root, 'http://host/'),
            (200, {}, 'This is a fake resource.'))

    def test_validChild(self):
        self.assertResponse(
            (self.root, 'http://host/validChild'),
            (200, {}, 'This is a valid child resource.'))

    def test_invalidChild(self):
        self.assertResponse(
            (self.root, 'http://host/invalidChild'),
            (404, {}, None))


class TestDeferredRendering(BaseCase):
    class ResourceWithDeferreds(BaseTestResource):
        addSlash=True
        responseText = 'I should be wrapped in a Deferred.'
        def render(self, ctx):
            from twisted.internet import reactor
            d = defer.Deferred()
            reactor.callLater(
                0, d.callback, BaseTestResource.render(self, ctx))
            return d

        def child_deferred(self, ctx):
            from twisted.internet import reactor
            d = defer.Deferred()
            reactor.callLater(0, d.callback, BaseTestResource())
            return d
        
    def test_deferredRootResource(self):
        self.assertResponse(
            (self.ResourceWithDeferreds(), 'http://host/'),
            (200, {}, 'I should be wrapped in a Deferred.'))

    def test_deferredChild(self):
        self.assertResponse(
            (self.ResourceWithDeferreds(), 'http://host/deferred'),
            (200, {}, 'This is a fake resource.'))
