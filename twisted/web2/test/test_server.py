"""
A test harness for the twisted.web2 server.
"""

from zope.interfaces import implements
from twisted.web2 import http
from twisted.web2 import http_headers
from twisted.web2 import iweb
from twisted.web2 import server

class FakeChanRequest:
    implements(iweb.IChanRequest)

    def __init__(self, site):
        self.request_method = 'GET'
        self.prepathuri = ''
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

    def writeIntermediateResponse(code, headers=None):
        pass
    
    def writeHeaders(self, code, headers):
        pass

    def write(self, data):
        pass

    def finish(self):
        pass

    def abortConnection(self):
        pass

    def registerProducer(self, producer, streaming):
        pass

    def unregisterProducer(self):
        pass

    
