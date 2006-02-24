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
    def isCollection(self):
        """
        Checks whether this resource is a collection resource.
        @return: C{True} if this resource is a collection resource, C{False}
            otherwise.
        """

    def findChildren(self, depth):
        """
        Returns an iterable of child resources for the given depth.
        Because resources do not know their request URIs, chidren are returned
        as tuples C{(resource, uri)}, where C{resource} is the child resource
        and C{uri} is a URL path relative to this resource.
        @param depth: the search depth (one of "0", "1", or "infinity")
        @return: an iterable of tuples C{(resource, uri)}.
        """

    def hasProperty(self, property):
        """
        Checks whether the given property is defined on this resource.
        @param property: an empty L{davxml.WebDAVElement} instance.
        @return: C{True} if the given property is set on this resource, C{False}
            otherwise.
        """

    def readProperty(self, property):
        """
        Reads the given property on this resource.
        @param property: an empty L{davxml.WebDAVElement} instance.
        @return: a matching L{davxml.WebDAVElement} instance containing the
            value of the given property.
        @raise HTTPError: (containing a response with a status code of
            L{responsecode.CONFLICT}) if C{property} is not set on this
            resource.
        """

    def writeProperty(self, property):
        """
        Writes the given property on this resource.
        @param property: a L{davxml.WebDAVElement} instance.
        @raise HTTPError: (containing a response with a status code of
            L{responsecode.CONFLICT}) if C{property} is a read-only property.
        """

    def removeProperty(self, property):
        """
        Removes the given property from this resource.
        @param property: a L{davxml.WebDAVElement} instance.
        @raise HTTPError: (containing a response with a status code of
            L{responsecode.CONFLICT}) if C{property} is a read-only property or
            if the property does not exist.
        """
