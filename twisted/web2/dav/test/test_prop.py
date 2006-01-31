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

import random

from twisted.trial.unittest import SkipTest
from twisted.web2 import responsecode
from twisted.web2.iweb import IResponse
from twisted.web2.stream import MemoryStream
from twisted.web2 import http_headers
from twisted.web2.dav import davxml
from twisted.web2.dav.util import davXMLFromStream
from twisted.web2.dav.test.util import SimpleRequest
import twisted.web2.dav.test.util

class PROP(twisted.web2.dav.test.util.TestCase):
    """
    PROPFIND, PROPPATCH requests
    """
    def test_PROPFIND(self):
        """
        PROPFIND request
        """
        live_properties = (
            davxml.GETContentLength(),
            davxml.GETContentType(),
            davxml.GETETag(),
            davxml.GETLastModified(),
        )

        def check_xml(doc):
            multistatus = doc.root_element

            if not isinstance(multistatus, davxml.MultiStatus):
                self.fail("PROPFIND response XML root element is not multistatus: %r" % (multistatus,))

            for response in multistatus.childrenOfType(davxml.PropertyStatusResponse):
                properties_to_find = [p.qname() for p in live_properties]

                if response.childOfType(davxml.HRef) == "/":
                    for propstat in response.childrenOfType(davxml.PropertyStatus):
                        status = propstat.childOfType(davxml.Status)
                        properties = propstat.childOfType(davxml.PropertyContainer).children

                        if status.code != responsecode.OK:
                            self.fail("PROPFIND failed (status %s) to locate live properties: %r"
                                      % (status.code, properties))

                        for property in properties:
                            qname = property.qname()
                            if qname in properties_to_find:
                                properties_to_find.remove(qname)
                            else:
                                self.fail("PROPFIND found property we didn't ask for: %r" % (property,))
                    break

            else:
                self.fail("No response for URI /")

        def check_result(response):
            response = IResponse(response)

            if response.code != responsecode.MULTI_STATUS:
                self.fail("Incorrect response code for PROPFIND (%s != %s)"
                          % (response.code, responsecode.MULTI_STATUS))

            content_type = response.headers.getHeader("content-type")
            if content_type not in (http_headers.MimeType("text", "xml"),
                                    http_headers.MimeType("application", "xml")):
                self.fail("Incorrect content-type for PROPFIND response (%r not in %r)"
                          % (content_type, (http_headers.MimeType("text", "xml"),
                                            http_headers.MimeType("application", "xml"))))

            return davXMLFromStream(response.stream).addCallback(check_xml)

        query = davxml.PropertyFind(davxml.PropertyContainer(*live_properties))

        request = SimpleRequest(self.site, "PROPFIND", "/")

        depth = random.choice(("0", "1", "infinity", None))
        if depth is not None:
            request.headers.setHeader("depth", "0")

        request.stream = MemoryStream(query.toxml())

        return self.send(request, check_result)

    def test_PROPPATCH(self):
        """
        PROPPATCH request
        """
        # FIXME:
        # PROPPATCH and PROPFIND some dead properties
        # Test allprop, propname lookups
        # Test nonexistant property
        # Test nonexistant resource
        # Response is text/xml or application/xml
        # Test None namespace in property
        # Try setting a live prop
        raise SkipTest("test unimplemented")
