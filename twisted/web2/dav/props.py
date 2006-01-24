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

import UserDict

from twisted.python import log

from twisted.web2.dav import davxml
from twisted.web2.dav.davxml import dav_namespace

class WebDAVPropertyStore (object, UserDict.DictMixin):
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

    overridableLiveProperties = (
        ((dav_namespace, "getcontenttype"), davxml.GETContentType),
        ((dav_namespace, "displayname"   ), davxml.DisplayName   ),
    )

    def __init__(self, resource):
        self.resource = resource
        self.deadProperties = resource.deadProperties

    def __getitem__(self, key):
        namespace, name = key

        if namespace == dav_namespace:
            if name == "resourcetype":
                # Allow live property to be overriden by dead property
                if key in self.deadProperties:
                    return self.deadProperties[key]
                if self.resource.isCollection():
                    return davxml.ResourceType.collection
                return davxml.ResourceType.empty
    
            if name == "getetag":
                return davxml.GETETag.fromString(self.resource.etag().generate())
    
            if name == "getcontenttype":
                return davxml.GETContentType.fromString(self.resource.contentType())
        
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

        return self.deadProperties[key]

    def __setitem__(self, key, value):
        assert isinstance(value, davxml.WebDAVElement)

        for qname, clazz in self.overridableLiveProperties:
            if key == qname:
                if not isinstance(value, clazz):
                    raise ValueError("Invalid value for %s property: %r" % (key, value))
                else:
                    break
        else:
            if key in self.liveProperties:
                raise ValueError("Live property %r cannot be set." % (key,))

        self.deadProperties[key] = value

        # Update the resource because we've modified it
        self.resource.fp.restat()

    def __delitem__(self, key):
        if key in self.liveProperties:
            raise ValueError("Live property %s cannot be removed." % (key,))

        del(self.deadProperties[key])

    def __contains__(self, key):
        return key in self.liveProperties or key in self.deadProperties

    def __iter__(self):
        for key in self.liveProperties: yield key
        for key in self.deadProperties: yield key

    def keys(self):
        return tuple(self.liveProperties) + tuple(self.deadProperties)

    def allpropKeys(self):
        keys = []

        for key in self.keys():
            if key in davxml.elements_by_tag_name:
                element_class = davxml.elements_by_tag_name[key]
                if not element_class.hidden:
                    keys.append(key)

        return keys
