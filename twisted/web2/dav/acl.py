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
WebDAV ACL resources.
"""

__all__ = ["DAVPrincipalResource"]

from zope.interface import implements
from twisted.internet.defer import maybeDeferred
from twisted.web2.dav import davxml
from twisted.web2.dav.davxml import dav_namespace
from twisted.web2.dav.idav import IDAVPrincipalResource
from twisted.web2.dav.resource import DAVLeafResource
from twisted.web2.dav.util import unimplemented

class DAVPrincipalResource (DAVLeafResource):
    """
    Resource representing a WebDAV principal.  (RFC 3744, section 2)
    """
    implements(IDAVPrincipalResource)

    ##
    # WebDAV
    ##

    liveProperties = DAVLeafResource.liveProperties + (
        (dav_namespace, "alternate-uri-set"),
        (dav_namespace, "principal-url"    ),
        (dav_namespace, "group-member-set" ),
        (dav_namespace, "group-membership" ),
    )

    def davComplianceClasses(self):
        return ("1",)

    def isCollection(self):
        return False

    def findChildren(self, depth):
        return ()

    def readProperty(self, property, request):
        def defer():
            if type(property) is tuple:
                qname = property
                sname = "{%s}%s" % property
            else:
                qname = property.qname()
                sname = property.sname()

            namespace, name = qname

            if namespace == dav_namespace:
                if name == "alternate-uri-set":
                    return davxml.AlternateURISet(*[davxml.HRef(u) for u in self.alternateURIs()])

                if name == "principal-url":
                    return davxml.PrincipalURL(davxml.HRef(self.principalURL()))

                if name == "group-member-set":
                    return davxml.GroupMemberSet(*[davxml.HRef(p) for p in self.groupMembers()])

                if name == "group-membership":
                    return davxml.GroupMemberSet(*[davxml.HRef(g) for g in self.groupMemberships()])

            return super(DAVPrincipalResource, self).readProperty(qname, request)

        return maybeDeferred(defer)

    ##
    # ACL
    ##

    def alternateURIs(self):
        """
        See L{IDAVPrincipalResource.alternateURIs}.

        This implementation returns C{()}.  Subclasses should override this
        method to provide alternate URIs for this resource if appropriate.
        """
        return ()

    def principalURL(self):
        """
        See L{IDAVPrincipalResource.principalURL}.

        This implementation raises L{NotImplementedError}.  Subclasses must
        override this method to provide the principal URL for this resource.
        """
        unimplemented(self)

    def groupMembers(self):
        """
        See L{IDAVPrincipalResource.groupMembers}.

        This implementation returns C{()}, which is appropriate for non-group
        principals.  Subclasses should override this method to provide member
        URLs for this resource if appropriate.
        """
        return ()

    def groupMemberships(self):
        """
        See L{IDAVPrincipalResource.groupMemberships}.

        This implementation raises L{NotImplementedError}.  Subclasses must
        override this method to provide the group URLs for this resource.
        """
        unimplemented(self)
  
