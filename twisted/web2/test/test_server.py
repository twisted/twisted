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

class FakeChanRequest:
    implements(iweb.IChanRequest)

    def __init__(self, site):
        self.request_method = 'GET'
        self.prepath = ''
        self.uri = ''
        self.http_version = (1, 1)
        self.site = site
        self.headers = http_headers.Headers()
        self.request = server.Request(self,
                                      self.request_method,
                                      self.uri,
                                      self.http_version,
                                      self.headers,
                                      site=self.site,
                                      prepathuri=self.prepath)

        self.data = ''
        self.responseHeaders = None
        self.code = None

    def writeIntermediateResponse(code, headers=None):
        pass
    
    def writeHeaders(self, code, headers):
        self.responseHeaders = headers
        self.code = code
        
    def write(self, data):
        self.data += data

    def finish(self):
        self.finished = True

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

class FakeResource(resource.Resource):
    responseCode = 200
    responseText = 'This is a fake resource.'

    def render(self, ctx):
        return http.Response(self.responseCode, stream=self.responseStream())

    def responseStream(self):
        return stream.MemoryStream(self.responseText)

    def child_validChild(self, ctx):
        f = FakeResource()
        f.responseCode = 200
        f.responseText = 'This is a valid child resource.'
        return f

    def child_missingChild(self, ctx):
        f = FakeResource()
        f.responseCode = 404
        f.responseStream = lambda self: None
        return f



class TestTest(unittest.TestCase):
    def setUp(self):
        self.root = FakeResource()
        self.site = server.Site(self.root)
        
    def chanrequest(self):
        return FakeChanRequest(self.site)

    def request(self, path, headers, version=(1,1)):
        return http.Request(self.chanrequest(), 'GET', path, version, headers)
        
