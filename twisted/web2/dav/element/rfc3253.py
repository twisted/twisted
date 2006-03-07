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

"""
RFC 3253 (Versioning Extensions to WebDAV) XML Elements

This module provides XML element definitions for use with WebDAV.

See RFC 3253: http://www.ietf.org/rfc/rfc3253.txt
"""

from twisted.web2.dav.element.base import *

##
# Section 1
##

class Error (WebDAVElement):
    """
    Specifies an error condition. (RFC 3253, section 1.6)
    """
    # FIXME: RFC 3253 doesn't quite seem to define this element...
    # FIXME: Move when we update to RFC 2518bis
    name = "error"

    allowed_children = { WebDAVElement: (0, None) }

##
# Section 3
##

class Comment (WebDAVTextElement):
    """
    Property used to track a brief comment about a resource that is suitable for
    presentation to a user. On a version, can be used to indicate why that
    version was created. (RFC 3253, section 3.1.1)
    """
    name = "comment"
    hidden = True

class CreatorDisplayName (WebDAVTextElement):
    """
    Property which contains a description of the creator of the resource that is
    suitable for presentation to a user. (RFC 3253, section 3.1.2)
    """
    name = "creator-displayname"
    hidden = True

class SupportedMethod (WebDAVElement):
    """
    Property which identifies a method that is supported by a resource. A method
    is supported by a resource if there is some state of that resource for which
    an application of that method will successfully satisfy all postconditions
    of that method, including any additional postconditions added by the
    features supported by that resource. (RFC 3253, section 3.1.3)
    """
    name = "supported-method"
    hidden = True

    allowed_children = { WebDAVElement: (0, None) }
    allowed_attributes = { "name": True }

class SupportedMethodSet (WebDAVElement):
    """
    Property which identifies the methods that are supported by a resource. (RFC
    3253, section 3.1.3)
    """
    name = "supported-method-set"
    protected = True
    hidden = True

    allowed_children = { (dav_namespace, "supported-method"): (0, None) }

class SupportedLiveProperty (WebDAVElement):
    """
    Property which identifies a live property that is supported by a resource. A
    live property is supported by a resource if that property has the semantics
    defined for that property.  The value of this property must identify all
    live properties defined by this document that are supported by the resource
    and should identify all live properties that are supported by the resource.
    (RFC 3253, section 3.1.4)
    """
    name = "supported-live-property"

    # FIXME: Where is the name element defined?
    allowed_children = { (dav_namespace, "name"): (1, 1) }

class SupportedLivePropertySet (WebDAVElement):
    """
    Property which identifies the live properties that are supported by a
    resource. (RFC 3253, section 3.1.4)
    """
    name = "supported-live-property-set"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "supported-live-property"): (0, None) }

class Report (WebDAVElement):
    """
    A report. (RFC 3253, section 3.1.5)
    """
    # FIXME: Section 3.1.5 is pretty low on information.  Where else do we look?
    name = "report"

    allowed_children = { WebDAVElement: (0, None) }

class SupportedReport (WebDAVElement):
    """
    Identifies a report that is supported by the resource.  (RFC 3253, section
    3.1.5)
    """
    name = "supported-report"

    #
    # FIXME:
    #
    #   RFC 3253, section 3.1.5 defines supported-report as:
    #
    #     <!ELEMENT supported-report report>
    #
    #   Which means that a report child element is required.  However, section
    # 3.6 defined a precondition with the same name (DAV:supported-report),
    # which means that, according to section 1.6.1, this XML must be issued if
    # the precondition fails:
    #
    #     <?xml version="1.0"?>
    #     <D:error xmlns:D="DAV:">
    #      <D:supported-report/>
    #     </D:error>
    #
    #   Which is a problem because here we use supported-report with no
    # children.
    #
    #   Absent any better guidance, we'll allow no children for this element for
    # the time being.
    #
    allowed_children = { (dav_namespace, "report"): (0, 1) }

class SupportedReportSet (WebDAVElement):
    """
    Property which identifies the reports that are supported by the resource.
    (RFC 3253, section 3.1.5)
    """
    name = "supported-report-set"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "supported-report"): (0, None) }

class ExpandProperty (WebDAVElement):
    """
    Report which provides a mechanism for retrieving in one request the
    properties from resources identified by DAV:href property values.
    (RFC 3253, section 3.8)
    """
    name = "expand-property"

    allowed_children = { (dav_namespace, "property"): (0, None) }

class Property (WebDAVElement):
    """
    Identifies a property by name. (RFC 3253, section 3.8)
    Principal which matches a user if the value of the identified property of a
    resource contains at most one DAV:href element, the value of that element
    identifies a principal, and the user matches that principal. (RFC 3744,
    section 5.5.1)
    """
    name = "property"

    allowed_children = { (dav_namespace, "property"): (0, None) }
    allowed_attributes = {
        "name"      : True,
        "namespace" : False,
    }
