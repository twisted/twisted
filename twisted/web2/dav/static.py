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
WebDAV-aware static resources.
"""

__all__ = ["DAVFile"]

from twisted.python import log
from twisted.web2.static import File
from twisted.web2.dav import davxml
from twisted.web2.dav.idav import IDAVResource
from twisted.web2.dav.resource import DAVResource
from twisted.web2.dav.util import bindMethods

try:
    from twisted.web2.dav.xattrprops import xattrPropertyStore as DeadPropertyStore
except ImportError:
    log.msg("No dead property store available; using nonePropertyStore.")
    log.msg("Setting of dead properties will not be allowed.")
    from twisted.web2.dav.noneprops import NonePropertyStore as DeadPropertyStore

class DAVFile (DAVResource, File):
    """
    WebDAV-accessible File resource.

    Extends twisted.web2.static.File to handle WebDAV methods.
    """
    def __init__(self, path,
                 defaultType="text/plain",
                 indexNames=None):
        """
        @param path: the path of the file backing this resource.
        @param defaultType: the default mime type (as a string) for this
            resource and (eg. child) resources derived from it.
        @param indexNames: a sequence of index file names.
        @param acl: an L{IDAVAccessControlList} with the .
        """
        super(DAVFile, self).__init__(path,
                                      defaultType = defaultType,
                                      ignoredExts = (),
                                      processors  = None,
                                      indexNames  = indexNames)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.fp.path)

    ##
    # WebDAV
    ##

    def davComplianceClasses(self):
        return ("1",) # Add "2" when we have locking

    def deadProperties(self):
        if not hasattr(self, "_dead_properties"):
            self._dead_properties = DeadPropertyStore(self)
        return self._dead_properties

    def isCollection(self):
        """
        See L{IDAVResource.isCollection}.
        """
        for child in self.listChildren(): return True
        return self.fp.isdir()

    def findChildren(self, depth):
        """
        See L{IDAVResource.findChildren}.
        """
        assert depth in ("0", "1", "infinity"), "Invalid depth: %s" % (depth,)
        if depth != "0" and self.isCollection():
            for name in self.listChildren():
                try:
                    child = IDAVResource(self.getChild(name))
                except TypeError:
                    child = None

                if child is not None:
                    if child.isCollection():
                        yield (child, name + "/")
                        if depth == "infinity":
                            for grandchild in child.findChildren(depth):
                                yield (grandchild[0], name + "/" + grandchild[1])
                    else:
                        yield (child, name)

    ##
    # ACL
    ##

    def supportedPrivileges(self):
        if not hasattr(DAVFile, "_supportedPrivilegeSet"):
            DAVFile._supportedPrivilegeSet = davxml.SupportedPrivilegeSet(
                davxml.SupportedPrivilege(
                    davxml.Privilege(davxml.All()),
                    davxml.Description("all privileges", **{"xml:lang": "en"}),
                    davxml.SupportedPrivilege(
                        davxml.Privilege(davxml.Read()),
                        davxml.Description("read resource", **{"xml:lang": "en"}),
                    ),
                    davxml.SupportedPrivilege(
                        davxml.Privilege(davxml.Write()),
                        davxml.Description("write resource", **{"xml:lang": "en"}),
                        davxml.SupportedPrivilege(
                            davxml.Privilege(davxml.WriteProperties()),
                            davxml.Description("write resource properties", **{"xml:lang": "en"}),
                        ),
                        davxml.SupportedPrivilege(
                            davxml.Privilege(davxml.WriteContent()),
                            davxml.Description("write resource content", **{"xml:lang": "en"}),
                        ),
                        davxml.SupportedPrivilege(
                            davxml.Privilege(davxml.Bind()),
                            davxml.Description("add child resource", **{"xml:lang": "en"}),
                        ),
                        davxml.SupportedPrivilege(
                            davxml.Privilege(davxml.Unbind()),
                            davxml.Description("remove child resource", **{"xml:lang": "en"}),
                        ),
                    ),
                    davxml.SupportedPrivilege(
                        davxml.Privilege(davxml.Unlock()),
                        davxml.Description("unlock resource without ownership", **{"xml:lang": "en"}),
                    ),
                    davxml.SupportedPrivilege(
                        davxml.Privilege(davxml.ReadACL()),
                        davxml.Description("read resource access control list", **{"xml:lang": "en"}),
                    ),
                    davxml.SupportedPrivilege(
                        davxml.Privilege(davxml.WriteACL()),
                        davxml.Description("write resource access control list", **{"xml:lang": "en"}),
                    ),
                    davxml.SupportedPrivilege(
                        davxml.Privilege(davxml.ReadCurrentUserPrivilegeSet()),
                        davxml.Description("read privileges for current principal", **{"xml:lang": "en"}),
                    ),
                ),
            )
        return DAVFile._supportedPrivilegeSet

    ##
    # Workarounds for issues with File
    ##

    def ignoreExt(self, ext):
        """
        Does nothing; doesn't apply to this subclass.
        """
        pass

    def createSimilarFile(self, path):
        return self.__class__(path, defaultType=self.defaultType, indexNames=self.indexNames[:])

#
# Attach method handlers to DAVFile
#

import twisted.web2.dav.method

bindMethods(twisted.web2.dav.method, DAVFile)
