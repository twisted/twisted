from __future__ import nested_scopes

import time
from twisted.trial import unittest
from twisted.web2 import http, http_headers, responsecode

class PreconditionTestCase(unittest.TestCase):
    def checkPreconditions(self, request, expectedResult, expectedCode,
                           initCode=responsecode.OK, entityExists=True):
        code=initCode
        request.setResponseCode(code)
        preconditionsPass = True
        
        try:
            request.checkPreconditions(entityExists=entityExists)
        except http.HTTPError, e:
            preconditionsPass = False
            code = e.code
        self.assertEquals(preconditionsPass, expectedResult)
        self.assertEquals(code, expectedCode)

    def testWithoutHeaders(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.out_headers.removeHeader("ETag")
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        self.checkPreconditions(request, True, responsecode.OK)

        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        self.checkPreconditions(request, True, responsecode.OK)
        
    def testIfMatch(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())

        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT

        # behavior of entityExists
        request.in_headers.setRawHeaders("If-Match", ('*',))
        self.checkPreconditions(request, True, responsecode.OK)
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED, entityExists=False)

        # tag matches
        request.in_headers.setRawHeaders("If-Match", ('"frob", "foo"',))
        self.checkPreconditions(request, True, responsecode.OK)

        # none match
        request.in_headers.setRawHeaders("If-Match", ('"baz", "bob"',))
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)
        
        # Must only compare strong tags
        request.out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.in_headers.setRawHeaders("If-Match", ('W/"foo"',))
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)

        
    def testIfUnmodifiedSince(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT

        request.in_headers.setRawHeaders("If-Unmodified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.in_headers.setRawHeaders("If-Unmodified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)

        # invalid date => header ignored
        request.in_headers.setRawHeaders("If-Unmodified-Since", ('alalalalalalalalalala',))
        self.checkPreconditions(request, True, responsecode.OK)


    def testIfModifiedSince(self):
        if time.time() < 946771200:
            raise "Your computer's clock is way wrong, this test will be invalid."
        
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)

        # invalid date => header ignored
        request.in_headers.setRawHeaders("If-Modified-Since", ('alalalalalalalalalala',))
        self.checkPreconditions(request, True, responsecode.OK)

        # date in the future => assume modified
        request.in_headers.setHeader("If-Modified-Since", time.time() + 500)
        self.checkPreconditions(request, True, responsecode.OK)

    def testIfNoneMatch(self):
        request = http.Request(None, "GET", "/", "HTTP/1.1", http_headers.Headers())
        request.out_headers.setHeader("ETag", http_headers.ETag('foo'))
        request.out_headers.setHeader("Last-Modified", 946771200) # Sun, 02 Jan 2000 00:00:00 GMT
        
        # behavior of entityExists
        request.in_headers.setRawHeaders("If-None-Match", ('*',))
        request.method="PUT"
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)
        self.checkPreconditions(request, True, responsecode.OK, entityExists=False)

        # tag matches
        request.in_headers.setRawHeaders("If-None-Match", ('"frob", "foo"',))
        request.method="PUT"
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)

        # now with IMS, also:
        request.in_headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        request.method="PUT"
        self.checkPreconditions(request, False, responsecode.PRECONDITION_FAILED)
        request.method="GET"
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)

        request.in_headers.removeHeader("If-Modified-Since")
        
        
        # none match
        request.in_headers.setRawHeaders("If-None-Match", ('"baz", "bob"',))
        self.checkPreconditions(request, True, responsecode.OK)

        # now with IMS, also:
        request.in_headers.setRawHeaders("If-Modified-Since", ('Mon, 03 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)
        
        request.in_headers.setRawHeaders("If-Modified-Since", ('Sat, 01 Jan 2000 00:00:00 GMT',))
        self.checkPreconditions(request, True, responsecode.OK)

        request.in_headers.removeHeader("If-Modified-Since")

        # But if we have an error code already, ignore this header
        self.checkPreconditions(request, True, responsecode.INTERNAL_SERVER_ERROR,
                                initCode=responsecode.INTERNAL_SERVER_ERROR)
        
        # Weak tags okay for GET
        request.out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.in_headers.setRawHeaders("If-None-Match", ('W/"foo"',))
        self.checkPreconditions(request, False, responsecode.NOT_MODIFIED)

        # Weak tags not okay for other methods
        request.method="PUT"
        request.out_headers.setHeader("ETag", http_headers.ETag('foo', weak=True))
        request.in_headers.setRawHeaders("If-None-Match", ('W/"foo"',))
        self.checkPreconditions(request, True, responsecode.OK)


