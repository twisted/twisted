"""
A test harness for the twisted.web2 server.
"""

from zope.interface import implements
from twisted.web2 import http, http_headers, iweb, server, responsecode
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

from twisted.web2 import resource
from twisted.web2 import stream
from twisted.web2 import http
from twisted.web2 import responsecode

class TestResource(resource.Resource):
    responseCode = 200
    responseText = 'This is a fake resource.'
    addSlash = True

    def render(self, ctx):
        return http.Response(self.responseCode, stream=self.responseStream())

    def responseStream(self):
        return stream.MemoryStream(self.responseText)

    def child_validChild(self, ctx):
        f = TestResource()
        f.responseCode = 200
        f.responseText = 'This is a valid child resource.'
        return f

    def child_missingChild(self, ctx):
        f = TestResource()
        f.responseCode = 404
        f.responseStream = lambda self: None
        return f



class _TestingWebTests(unittest.TestCase):
    def setUp(self):
        self.root = TestResource()
        self.site = server.Site(self.root)
        
    def chanrequest(self, *args, **kw):
        return TestChanRequest(self.site, *args, **kw)

    def headers(self):
        return http_headers.Headers({
            'Content-Length': 0
            })

    def test_thatOurTestHarnessWorks(self):
        cr = self.chanrequest('GET', '', 'http://test-server/',
                              headers=self.headers())
        def _gotResponse((code, headers, data)):
            from twisted.web2 import responsecode
            self.assertEquals(code, 200)
            self.assertEquals(headers.getHeader('content-length'), 24)
            self.assertEquals(data, 'This is a fake resource.')
        cr.deferredFinish.addCallback(_gotResponse)
        cr.request.process()
        return cr

class _TestingBetterWebTests(unittest.TestCase):
    """
    This is also sub-optimal, but closer to what we want to do
    for testing resource lookup and rendering.
    """
    
    rootResource = TestResource()
    resourceTests = [
        ('GET', 'http://host/', 200, 'This is a fake resource.'),
        ('GET', 'http://host/', 200, 'This is a valid child resource.'),
        ('GET', 'http://host/', responsecode.NOT_FOUND),
        ]

    def doTest(self, method, uri,
               expected_code, expected_data=None, expected_headers=None):
        # Set up our initial conditions
        prepath = ''
        site = server.Site(self.rootResource)
        headers = http_headers.Headers({'content-length': 0})
        version = (1, 1)
        # Create our channel request
        cr = TestChanRequest(site, method, prepath, uri, headers, version)
        # When we get a response, we run our tests
        def _gotResponse((code, headers, data)):
            self.assertEquals(code, expected_code)
            if expected_data is not None:
                self.assertEquals(data, expected_data)
                self.assertEquals(headers.getHeader('content-length'),
                                  len(expected_data))
            if expected_headers is not None:
                for key, value in expected_headers.iteritems():
                    self.assertEquals(headers.getHeader(key), value)
        # Don't call us, we'll call you
        cr.deferredFinish.addCallback(_gotResponse)
        cr.request.process()
        return cr
        
    def test_runTests(self):
        for test_args in self.resourceTests:
            self.doTest(*test_args)
            
        
if __name__ == '__main__':
    tc = _TestingWebTests()
    tc.setUp()
    tc.test_thatOurTestHarnessWorks()
    from twisted.internet import reactor
    reactor.run()
    
