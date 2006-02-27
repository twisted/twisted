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
WebDAV Property store.

This API is considered private to static.py and is therefore subject to
change.
"""

__all__ = ["WebDAVPropertyStore"]

from twisted.python import log

from twisted.web2.dav import davxml
from twisted.web2.dav.davxml import dav_namespace
from twisted.web2.dav.davxml import lookupElement
from twisted.web2.http_headers import generateContentType

class WebDAVPropertyStore (object):
    """
    A mapping object of DAV properties for a DAV resource.
    Keys are the names of the associated properties, values are
    davxml.WebDAVElement instances.
    """

    liveProperties = (
        (dav_namespace, "resourcetype"    ),
        (dav_namespace, "getetag"         ),
        (dav_namespace, "getcontenttype"  ),
        (dav_namespace, "getcontentlength"),
        (dav_namespace, "getlastmodified" ),
        (dav_namespace, "creationdate"    ),
        (dav_namespace, "displayname"     ),
        (dav_namespace, "supportedlock"   ),
    )

    def __init__(self, resource, deadProperties):
        self.resource       = resource
        self.deadProperties = deadProperties

    def get(self, qname, request):
        namespace, name = qname

        if namespace == dav_namespace:
            if name == "resourcetype":
                # Allow live property to be overriden by dead property
                if self.deadProperties.contains(qname):
                    return self.deadProperties.get(qname)
                if self.resource.isCollection():
                    return davxml.ResourceType.collection
                return davxml.ResourceType.empty
    
            if name == "getetag":
                return davxml.GETETag.fromString(self.resource.etag().generate())
    
            if name == "getcontenttype":
                mimeType = self.resource.contentType()
                mimeType.params = None # WebDAV getcontenttype property does not include parameters
                return davxml.GETContentType.fromString(generateContentType(mimeType))
        
            if name == "getcontentlength":
                return davxml.GETContentLength.fromString(self.resource.contentLength())

            if name == "getlastmodified":
                return davxml.GETLastModified.fromDate(self.resource.lastModified())

            if name == "creationdate":
                return davxml.CreationDate.fromDate(self.resource.creationDate())

            if name == "displayname":
                return davxml.DisplayName.fromString(self.resource.displayName())

            if name == "supportedlock":
                return davxml.SupportedLock(
                    davxml.LockEntry(davxml.LockScope.exclusive, davxml.LockType.write),
                    davxml.LockEntry(davxml.LockScope.shared   , davxml.LockType.write),
                )

        return self.deadProperties.get(qname)

    def set(self, property, request):
        assert isinstance(property, davxml.WebDAVElement)

        if property.protected:
            raise ValueError("Protected property %r may be set." % (qname,))

        self.deadProperties.set(property)

        # Update the resource because we've modified it
        self.resource.fp.restat()

    def delete(self, qname, request):
        if qname in self.liveProperties:
            raise ValueError("Live property %s cannot be deleted." % (qname,))

        self.deadProperties.delete(qname)

    def contains(self, qname, request):
        return qname in self.liveProperties or self.deadProperties.contains(qname)

    def list(self, request):
        # FIXME: A set would be better here, that that's a python 2.4+ feature.

        qnames = list(self.liveProperties)

        for qname in self.deadProperties.list():
            qnames.append(qname)

        return qnames

    def allprop(self, request):
        """
        Some DAV properties should not be returned to a C{DAV:allprop} query.
        RFC 3253 defines several such properties.  This method computes a subset
        of the property qnames returned by L{list} by filtering out elements
        whose class have the C{.hidden} attribute set to C{True}.
        @return: a list of qnames of properties which are defined and are
            appropriate for use in response to a C{DAV:allprop} query.   
        """
        qnames = []

        for qname in self.list(request):
            try:
                if not lookupElement(qname).hidden:
                    qnames.append(qname)
            except KeyError:
                pass

        return qnames
