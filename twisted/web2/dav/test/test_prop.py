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
from twisted.web2.dav.resource import DAVResource
from twisted.web2.dav.davxml import dav_namespace, lookupElement
from twisted.web2.dav.util import davXMLFromStream
from twisted.web2.test.test_server import SimpleRequest
from twisted.web2.dav.test.util import serialize
import twisted.web2.dav.test.util

live_properties = [lookupElement(qname)() for qname in DAVResource.liveProperties if qname[0] == dav_namespace]

#
# See whether dead properties are available
#
from twisted.web2.dav.noneprops import NonePropertyStore
from twisted.web2.dav.static import DeadPropertyStore
if DeadPropertyStore == NonePropertyStore:
    have_dead_properties = False
else:
    have_dead_properties = True

class PROP(twisted.web2.dav.test.util.TestCase):
    """
    PROPFIND, PROPPATCH requests
    """
    def test_PROPFIND_basic(self):
        """
        PROPFIND request
        """
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

        def check_xml(doc):
            multistatus = doc.root_element

            if not isinstance(multistatus, davxml.MultiStatus):
                self.fail("PROPFIND response XML root element is not multistatus: %r" % (multistatus,))

            for response in multistatus.childrenOfType(davxml.PropertyStatusResponse):
                if response.childOfType(davxml.HRef) == "/":
                    for propstat in response.childrenOfType(davxml.PropertyStatus):
                        status = propstat.childOfType(davxml.Status)
                        properties = propstat.childOfType(davxml.PropertyContainer).children

                        if status.code != responsecode.OK:
                            self.fail("PROPFIND failed (status %s) to locate live properties: %s"
                                      % (status.code, properties))

                        properties_to_find = [p.qname() for p in live_properties]

                        for property in properties:
                            qname = property.qname()
                            if qname in properties_to_find:
                                properties_to_find.remove(qname)
                            else:
                                self.fail("PROPFIND found property we didn't ask for: %r" % (property,))

                        if properties_to_find:
                            self.fail("PROPFIND failed to find properties: %r" % (properties_to_find,))

                    break

            else:
                self.fail("No response for URI /")

        query = davxml.PropertyFind(davxml.PropertyContainer(*live_properties))

        request = SimpleRequest(self.site, "PROPFIND", "/")

        depth = random.choice(("0", "1", "infinity", None))
        if depth is not None:
            request.headers.setHeader("depth", depth)

        request.stream = MemoryStream(query.toxml())

        return self.send(request, check_result)

    def test_PROPFIND_list(self):
        """
        PROPFIND with allprop, propname
        """
        def check_result(which):
            def _check_result(response):
                response = IResponse(response)

                if response.code != responsecode.MULTI_STATUS:
                    self.fail("Incorrect response code for PROPFIND (%s != %s)"
                              % (response.code, responsecode.MULTI_STATUS))

                return davXMLFromStream(response.stream).addCallback(check_xml, which)
            return _check_result

        def check_xml(doc, which):
            response = doc.root_element.childOfType(davxml.PropertyStatusResponse)

            self.failUnless(
                response.childOfType(davxml.HRef) == "/",
                "Incorrect response URI: %s != /" % (response.childOfType(davxml.HRef),)
            )

            for propstat in response.childrenOfType(davxml.PropertyStatus):
                status = propstat.childOfType(davxml.Status)
                properties = propstat.childOfType(davxml.PropertyContainer).children

                if status.code != responsecode.OK:
                    self.fail("PROPFIND failed (status %s) to locate live properties: %s"
                              % (status.code, properties))

                if which.name == "allprop":
                    properties_to_find = [p.qname() for p in live_properties if not p.hidden]
                else:
                    properties_to_find = [p.qname() for p in live_properties]

                for property in properties:
                    qname = property.qname()
                    if qname in properties_to_find:
                        properties_to_find.remove(qname)
                    elif qname[0] != dav_namespace:
                        pass
                    else:
                        self.fail("PROPFIND with %s found property we didn't expect: %r" % (which.name, property))

                    if which.name == "propname":
                        # Element should be empty
                        self.failUnless(len(property.children) == 0)
                    else:
                        # Element should have a value
                        # Actually, this isn't necessarily true, but it is for the live
                        # properties we've defined so far...
                        self.failIf(len(property.children) == 0)

                if properties_to_find:
                    self.fail("PROPFIND with %s failed to find properties: %r" % (which.name, properties_to_find))

            properties = propstat.childOfType(davxml.PropertyContainer).children

        def work():
            for which in (davxml.AllProperties(), davxml.PropertyName()):
                query = davxml.PropertyFind(which)

                request = SimpleRequest(self.site, "PROPFIND", "/")
                request.headers.setHeader("depth", "0")
                request.stream = MemoryStream(query.toxml())

                yield (request, check_result(which))

        return serialize(self.send, work())

    def test_PROPPATCH_basic(self):
        """
        PROPPATCH
        """
        # FIXME:
        # Do PROPFIND to make sure it's still there
        # Test nonexistant resource
        # Test None namespace in property

        def check_patch_response(response):
            response = IResponse(response)

            if response.code != responsecode.MULTI_STATUS:
                self.fail("Incorrect response code for PROPFIND (%s != %s)"
                          % (response.code, responsecode.MULTI_STATUS))

            content_type = response.headers.getHeader("content-type")
            if content_type not in (http_headers.MimeType("text", "xml"),
                                    http_headers.MimeType("application", "xml")):
                self.fail("Incorrect content-type for PROPPATCH response (%r not in %r)"
                          % (content_type, (http_headers.MimeType("text", "xml"),
                                            http_headers.MimeType("application", "xml"))))

            return davXMLFromStream(response.stream).addCallback(check_patch_xml)

        def check_patch_xml(doc):
            multistatus = doc.root_element

            if not isinstance(multistatus, davxml.MultiStatus):
                self.fail("PROPFIND response XML root element is not multistatus: %r" % (multistatus,))

            # Requested a property change one resource, so there should be exactly one response
            response = multistatus.childOfType(davxml.Response)

            # Should have a response description (its contents are arbitrary)
            response.childOfType(davxml.ResponseDescription)

            # Requested property change was on /
            self.failUnless(
                response.childOfType(davxml.HRef) == "/",
                "Incorrect response URI: %s != /" % (response.childOfType(davxml.HRef),)
            )

            # Requested one property change, so there should be exactly one property status
            propstat = response.childOfType(davxml.PropertyStatus)

            # And the contained property should be a SpiffyProperty
            self.failIf(
                propstat.childOfType(davxml.PropertyContainer).childOfType(SpiffyProperty) is None,
                "Not a SpiffyProperty in PROPPATCH property status: %s" % (propstat.toxml())
            )

            if not have_dead_properties:
                raise SkipTest(
                    "No dead property store available for DAVFile.  "
                    "Install xattr (http://undefined.org/python/#xattr) to enable use of dead properties."
                )

            # And the status should be 200
            self.failUnless(
                propstat.childOfType(davxml.Status).code == responsecode.OK,
                "Incorrect status code for PROPPATCH of property %s: %s != %s"
                % (propstat.childOfType(davxml.PropertyContainer).toxml(),
                   propstat.childOfType(davxml.Status).code, responsecode.OK)
            )

        patch = davxml.PropertyUpdate(
            davxml.Set(
                davxml.PropertyContainer(
                    SpiffyProperty.fromString("This is a spiffy resource.")
                )
            )
        )

        request = SimpleRequest(self.site, "PROPPATCH", "/")
        request.stream = MemoryStream(patch.toxml())
        return self.send(request, check_patch_response)

    def test_PROPPATCH_liveprop(self):
        """
        PROPPATCH on a live property
        """
        prop = davxml.GETETag.fromString("some-etag-string")
        patch = davxml.PropertyUpdate(davxml.Set(davxml.PropertyContainer(prop)))

        return self._simple_PROPPATCH(patch, prop, responsecode.FORBIDDEN, "edit of live property")

    def test_PROPPATCH_exists_not(self):
        """
        PROPPATCH remove a non-existant property
        """
        prop = davxml.Timeout() # Timeout isn't a valid property, so it won't exist.
        patch = davxml.PropertyUpdate(davxml.Remove(davxml.PropertyContainer(prop)))

        return self._simple_PROPPATCH(patch, prop, responsecode.OK, "remove of non-existant property")

    def _simple_PROPPATCH(self, patch, prop, expected_code, what):
        def check_result(response):
            response = IResponse(response)

            if response.code != responsecode.MULTI_STATUS:
                self.fail("Incorrect response code for PROPPATCH (%s != %s)"
                          % (response.code, responsecode.MULTI_STATUS))

            return davXMLFromStream(response.stream).addCallback(check_xml)

        def check_xml(doc):
            response = doc.root_element.childOfType(davxml.Response)
            propstat = response.childOfType(davxml.PropertyStatus)

            self.failUnless(
                response.childOfType(davxml.HRef) == "/",
                "Incorrect response URI: %s != /" % (response.childOfType(davxml.HRef),)
            )

            self.failIf(
                propstat.childOfType(davxml.PropertyContainer).childOfType(prop) is None,
                "Not a %s in PROPPATCH property status: %s" % (prop.sname(), propstat.toxml())
            )

            if not have_dead_properties:
                raise SkipTest(
                    "No dead property store available for DAVFile.  "
                    "Install xattr (http://undefined.org/python/#xattr) to enable use of dead properties."
                )

            self.failUnless(
                propstat.childOfType(davxml.Status).code == expected_code,
                "Incorrect status code for PROPPATCH %s: %s != %s"
                % (what, propstat.childOfType(davxml.Status).code, expected_code)
            )

        request = SimpleRequest(self.site, "PROPPATCH", "/")
        request.stream = MemoryStream(patch.toxml())
        return self.send(request, check_result)

class SpiffyProperty (davxml.WebDAVTextElement):
    namespace = "http://twistedmatrix.com/ns/private/tests"
    name = "spiffyproperty"
