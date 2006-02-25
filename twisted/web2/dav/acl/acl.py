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

__all__ = ["DAVPrincipalCollection", "DAVPrincipalResource"]

from twisted.web2.resource import LeafResource
from twisted.web2.dav.resource import DAVResource, DAVLeafResource

class DAVPrincipalCollection (DAVResource):
    """
    Collection resource which contains principal resources.
    """
    def davComplianceClasses(self):
        return ("1",)

    def isCollection(self):
        return True

    def findChildren(self, depth):
        if depth != "0":
            raise HTTPError(StatusResponse(
                responsecode.FORBIDDEN,
                "PROFIND with depth %s is not allowed in principal collection resources" % (depth,)
            ))

        return ()

class DAVPrincipalResource (DAVLeafResource):
    """
    Resource representing a WebDAV principal.  (RFC 3744, section 2)
    """
    ##
    # WebDAV
    ##

    def davComplianceClasses(self):
        return ("1",)

    def isCollection(self):
        return True

    def findChildren(self, depth):
        return ()

    ##
    # ACL
    ##

    def alternateURIs(self):
        """
        Provides the URIs of network resources with additional descriptive
        information about the principal, for example, a URI to an LDAP record.
        (RFC 3744, section 4.1)

        This implementation returns C{()}.  Subclasses should override this
        method to provide alternate URIs for this resource if appropriate.

        @return: a iterable of URIs.
        """
        return ()

    def principalURL(self):
        """
        Provides the URL which must be used to identify this principal in ACL
        requests.  (RFC 3744, section 4.2)

        This implementation raises L{NotImplementedError}.  Subclasses must
        override this method to provide the principal URL for this resource.

        @return: a URL.
        """
        raise NotImplementedError("Subclass must implement principalURL()")

    def groupMembers(self):
        """
        Provides the principal URLs of principals that are direct members of
        this (group) principal.  (RFC 3744, section 4.3)

        This implementation returns C{()}, which is appropriate for non-group
        principals.  Subclasses should override this method to provide member
        URLs for this resource if appropriate.

        @return: a iterable of principal URLs.
        """
        return ()

    def groups(self):
        """
        Provides the URLs of the group principals in which the principal is
        directly a member.  (RFC 3744, section 4.4)

        This implementation raises L{NotImplementedError}.  Subclasses must
        override this method to provide the group URLs for this resource.

        @return: a iterable of group principal URLs.
        """
        raise NotImplementedError("Subclass must implement groups()")
