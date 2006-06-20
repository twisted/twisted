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
web2.dav interfaces.
"""

__all__ = [ "IDAVResource" ]

from twisted.web2.iweb import IResource

class IDAVResource(IResource):
    """
    WebDAV resource.
    """
    def isCollection():
        """
        Checks whether this resource is a collection resource.
        @return: C{True} if this resource is a collection resource, C{False}
            otherwise.
        """

    def findChildren(depth):
        """
        Returns an iterable of child resources for the given depth.
        Because resources do not know their request URIs, chidren are returned
        as tuples C{(resource, uri)}, where C{resource} is the child resource
        and C{uri} is a URL path relative to this resource.
        @param depth: the search depth (one of C{"0"}, C{"1"}, or C{"infinity"})
        @return: an iterable of tuples C{(resource, uri)}.
        """

    def hasProperty(property, request):
        """
        Checks whether the given property is defined on this resource.
        @param property: an empty L{davxml.WebDAVElement} instance or a qname
            tuple.
        @param request: the request being processed.
        @return: a deferred value of C{True} if the given property is set on
            this resource, or C{False} otherwise.
        """

    def readProperty(property, request):
        """
        Reads the given property on this resource.
        @param property: an empty L{davxml.WebDAVElement} class or instance, or
            a qname tuple.
        @param request: the request being processed.
        @return: a deferred L{davxml.WebDAVElement} instance
            containing the value of the given property.
        @raise HTTPError: (containing a response with a status code of
            L{responsecode.CONFLICT}) if C{property} is not set on this
            resource.
        """

    def writeProperty(property, request):
        """
        Writes the given property on this resource.
        @param property: a L{davxml.WebDAVElement} instance.
        @param request: the request being processed.
        @return: an empty deferred which fires when the operation is completed.
        @raise HTTPError: (containing a response with a status code of
            L{responsecode.CONFLICT}) if C{property} is a read-only property.
        """

    def removeProperty(property, request):
        """
        Removes the given property from this resource.
        @param property: a L{davxml.WebDAVElement} instance or a qname tuple.
        @param request: the request being processed.
        @return: an empty deferred which fires when the operation is completed.
        @raise HTTPError: (containing a response with a status code of
            L{responsecode.CONFLICT}) if C{property} is a read-only property or
            if the property does not exist.
        """

    def listProperties(request):
        """
        @param request: the request being processed.
        @return: a deferred iterable of qnames for all properties defined for
            this resource.
        """

    def principalCollections():
        """
        Provides the URIs of collection resources which contain principal
        resources which may be used in access control entries on this resource.
        (RFC 3744, section 5.8)
        @return: a sequence of URIs referring to collection resources which
            implement the C{DAV:principal-property-search} C{REPORT}.
        """

    def accessControlList():
        """
        @return: the L{davxml.ACL} element containing the access control list
            for this resource.
        """

    def supportedPrivileges():
        """
        @return: a sequence of the access control privileges which are
            supported by this resource.
        """

class IDAVPrincipalResource (IDAVResource):
    """
    WebDAV principal resource.  (RFC 3744, section 2)
    """
    def alternateURIs():
        """
        Provides the URIs of network resources with additional descriptive
        information about the principal, for example, a URI to an LDAP record.
        (RFC 3744, section 4.1)
        @return: a iterable of URIs.
        """

    def principalURL():
        """
        Provides the URL which must be used to identify this principal in ACL
        requests.  (RFC 3744, section 4.2)
        @return: a URL.
        """

    def groupMembers():
        """
        Provides the principal URLs of principals that are direct members of
        this (group) principal.  (RFC 3744, section 4.3)
        @return: a iterable of principal URLs.
        """

    def groupMemberships():
        """
        Provides the URLs of the group principals in which the principal is
        directly a member.  (RFC 3744, section 4.4)
        @return: a iterable of group principal URLs.
        """
