##
# Copyright (c) 2005 Apple Computer, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DRI: Wilfredo Sanchez, wsanchez@apple.com
##

from twisted.web2.iweb import IResponse
from twisted.web2.stream import MemoryStream
from twisted.web2 import responsecode

import twisted.web2.dav.test.util
from twisted.web2.test.test_server import SimpleRequest
from twisted.web2.dav import davxml

class REPORT(twisted.web2.dav.test.util.TestCase):
    """
    REPORT request
    """
    def test_REPORT_no_body(self):
        """
        REPORT request with no body
        """
        def do_test(response):
            response = IResponse(response)

            if response.code != responsecode.BAD_REQUEST:
                self.fail("Unexpected response code for REPORT with no body: %s"
                          % (response.code,))

        request = SimpleRequest(self.site, "REPORT", "/")
        request.stream = MemoryStream("")

        return self.send(request, do_test)

    def test_REPORT_unknown(self):
        """
        Unknown/bogus report type
        """
        def do_test(response):
            response = IResponse(response)

            if response.code != responsecode.FORBIDDEN:
                self.fail("Unexpected response code for unknown REPORT: %s"
                          % (response.code,))
        class GoofyReport (davxml.WebDAVUnknownElement):
            namespace = "GOOFY:"
            name      = "goofy-report"
            def __init__(self): super(GoofyReport, self).__init__()

        request = SimpleRequest(self.site, "REPORT", "/")
        request.stream = MemoryStream(GoofyReport().toxml())

        return self.send(request, do_test)
