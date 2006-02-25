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

__all__ = ["DACLPropertyStore"]

from twisted.python import log

from twisted.web2.dav import davxml
from twisted.web2.dav.davxml import dav_namespace
from twisted.web2.dav.props import WebDAVPropertyStore

class DACLPropertyStore (WebDAVPropertyStore):
    """
    A mapping object of DAV properties for a WebDAV ACL principal resource.
    """
    liveProperties = WebDAVPropertyStore.liveProperties + (
    )

    def __getitem__(self, key):
        namespace, name = key

        if namespace == dav_namespace:
            if name == "alternate-uri-set":
                return davxml.AlternateURISet(*[davxml.HRef(u) for u in self.resource.alternateURIs()])

            if name == "principal-url":
                return davxml.PrincipalURL(davxml.HRef(self.resource.principalURL()))

            if name == "group-member-set":
                return davxml.GroupMemberSet(*[davxml.HRef(p) for p in self.resource.groupMembers()])

            if name == "group-membership":
                return davxml.GroupMemberSet(*[davxml.HRef(g) for g in self.resource.groupMemberships()])

        return super(DACLPropertyStore, self).__getitem__(key)
