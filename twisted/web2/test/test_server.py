"""
A test harness for the twisted.web2 server.
"""

from zope.interface import implements
from twisted.web2 import http
from twisted.web2 import http_headers
from twisted.web2 import iweb
from twisted.web2 import server
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
        self.data = ''
        self.responseHeaders = None
        self.code = None
        self.finish_callbacks = []

    def addFinishCallback(self, callback):
        self.finish_callbacks.append(callback)

    def writeIntermediateResponse(code, headers=None):
        pass
    
    def writeHeaders(self, code, headers):
        self.responseHeaders = headers
        self.code = code
        
    def write(self, data):
        self.data += data

    def finish(self):
        self.finished = True
        from twisted.internet import reactor
        for cb in self.finish_callbacks:
            reactor.callLater(
                0, cb, self.code, self.responseHeaders, self.data)

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
        def _gotResponse(code, headers, data):
            from twisted.web2 import responsecode
            self.assertEquals(code, 200)
            self.assertEquals(headers.getHeader('content-length'), 24)
            self.assertEquals(data, 'This is a fake resource.')
        cr.addFinishCallback(_gotResponse)
        cr.request.process()
        return cr



        
if __name__ == '__main__':
    tc = _TestingWebTests()
    tc.setUp()
    tc.test_thatOurTestHarnessWorks()
    from twisted.internet import reactor
    reactor.run()
    
