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
    def child_foo(self, ctx, segments):
        return self, segments[1:]

    def render(self, ctx):
        return http.Response(
            responsecode.OK,
            stream.MemoryStream("Ok"))

