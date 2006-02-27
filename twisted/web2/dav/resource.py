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
WebDAV resources.
"""

__all__ = [
    "DAVPropertyMixIn",
    "DAVResource",
    "DAVLeafResource"
]

import urllib

from zope.interface import implements
from twisted.python import log
from twisted.internet.defer import maybeDeferred
from twisted.web2 import responsecode
from twisted.web2.http import HTTPError, RedirectResponse
from twisted.web2.iweb import IResponse
from twisted.web2.resource import LeafResource
from twisted.web2.static import MetaDataMixin, StaticRenderMixin
from twisted.web2.dav import davxml
from twisted.web2.dav.idav import IDAVResource
from twisted.web2.dav.props import WebDAVPropertyStore

class DAVPropertyMixIn (MetaDataMixin):
    """
    Mix-in class which implements the DAV property access API in
    L{IDAVResource}.
    """
    def properties(self):
        """
        Provides internal access to the WebDAV property store.  You probably
        shouldn't be calling this directly if you can use the property accessors
        in the IDAVResource API instead.  However, a subclass may chose to
        override this method to provide it's own property store.

        Note that this property store contains both dead and live properties;
        live properties are often not writeable, whereas dead properties usually
        are (assuming you have permission).

        This implementation uses a L{twisted.web2.dav.WebDAVPropertyStore} which
        is constructed with the dead property store returned by
        L{deadProperties} and cached.

        @return: a dict-like object from which one can read and to which one can
            write properties.  Keys are qname tuples (ie. C{(namespace, name)})
            as returned by L{davxml.WebDAVElement.qname()} and values are
            L{davxml.WebDAVElement} instances.
        """
        if not hasattr(self, "_properties"):
            self._properties = WebDAVPropertyStore(self, self.deadProperties())
        return self._properties

    def deadProperties(self):
        """
        Provides internal access to the WebDAV dead property store.  You
        probably shouldn't be calling this directly if you can use the property
        accessors in the L{IDAVResource} API instead.  However, a subclass must
        override this method to provide it's own dead property store.

        This implementation raises L{NotImplementedError}.

        @return: a dict-like object from which one can read and to which one can
            write dead properties.  Keys are qname tuples (ie. C{(namespace, name)})
            as returned by L{davxml.WebDAVElement.qname()} and values are
            L{davxml.WebDAVElement} instances.
        """
        raise NotImplementedError("Subclass must implement deadProperties()")

    def hasProperty(self, property, request):
        """
        See L{IDAVResource.hasProperty}.
        """
        if type(property) is tuple:
            qname = property
        else:
            qname = property.qname()

        return self.properties().contains(qname, request)

    def readProperty(self, property, request):
        """
        See L{IDAVResource.readProperty}.
        """
        if type(property) is tuple:
            qname = property
            sname = "{%s}%s" % property
        else:
            qname = property.qname()
            sname = property.sname()

        return self.properties().get(qname, request)

    def writeProperty(self, property, request):
        """
        See L{IDAVResource.writeProperty}.
        """
        self.properties().set(property, request)

    def removeProperty(self, property, request):
        """
        See L{IDAVResource.removeProperty}.
        """
        if type(property) is tuple:
            qname = property
        else:
            qname = property.qname()

        self.properties().delete(qname, request)

    def hasDeadProperty(self, property):
        """
        Same as L{hasProperty}, but bypasses the live property store and checks
        directly from the dead property store.
        """
        if type(property) is tuple:
            qname = property
        else:
            qname = property.qname()

        return self.deadProperties().contains(qname)

    def readDeadProperty(self, property):
        """
        Same as L{readProperty}, but bypasses the live property store and reads
        directly from the dead property store.
        """
        if type(property) is tuple:
            qname = property
        else:
            qname = property.qname()

        return self.deadProperties().get(qname)

    def writeDeadProperty(self, property):
        """
        Same as L{writeProperty}, but bypasses the live property store and
        writes directly to the dead property store.
        Note that this should not be used unless you know that you are writing
        to an overrideable live property, as this bypasses the logic which
        protects protected properties.  The result of writing to a
        non-overrideable live property with this method is undefined; the value
        in the dead property store may or may not be ignored when reading the
        property with L{readProperty}.
        """
        self.deadProperties().set(property)

    #
    # Overrides some methods in MetaDataMixin in order to allow DAV properties
    # to override the values of some HTTP metadata.
    #
    def contentType(self):
        if self.hasDeadProperty((davxml.dav_namespace, "getcontenttype")):
            return self.readDeadProperty((davxml.dav_namespace, "getcontenttype")).mimeType()
        else:
            return super(DAVPropertyMixIn, self).contentType()

    def displayName(self):
        if self.hasDeadProperty((davxml.dav_namespace, "displayname")):
            return str(self.readDeadProperty((davxml.dav_namespace, "displayname")))
        else:
            return super(DAVPropertyMixIn, self).displayName()

class DAVResource (DAVPropertyMixIn, StaticRenderMixin):
    implements(IDAVResource)

    def isCollection(self):
        """
        See L{IDAVResource.isCollection}.
        This implementation raises L{NotImplementedError}; a subclass must
        override this method.
        """
        raise NotImplementedError("Subclass must implement isCollection()")

    def findChildren(self, depth):
        """
        See L{IDAVResource.findChildren}.
        This implementation raises L{NotImplementedError}; a subclass must
        override this method.
        """
        assert depth in ("0", "1", "infinity"), "Invalid depth: %s" % (depth,)
        if depth == "0" or not self.isCollection():
            return ()
        else:
            raise NotImplementedError("Subclass must implement findChildren()")

    def davComplianceClasses(self):
        """
        This implementation raises L{NotImplementedError}.
        @return: a sequence of strings denoting WebDAV compliance classes.  For
            example, a DAV level 2 server might return ("1", "2").
        """
        raise NotImplementedError("Subclass must implement davComplianceClasses()")

    def renderHTTP(self, request):

        # FIXME: This is for testing with litmus; comment out when not in use
        #litmus = request.headers.getRawHeaders("x-litmus")
        #if litmus: log.msg("*** Litmus test: %s ***" % (litmus,))

        # FIXME: Learn how to use twisted logging facility, wsanchez
        protocol = "HTTP/%s.%s" % request.clientproto
        log.msg("%s %s %s" % (request.method, urllib.unquote(request.uri), protocol))

        #
        # If this is a collection and the URI doesn't end in "/", redirect.
        #
        if self.isCollection() and request.uri[-1:] != "/":
            return RedirectResponse(request.uri + "/")

        def setHeaders(response):
            response = IResponse(response)

            response.headers.setHeader("dav", self.davComplianceClasses())

            #
            # If this is a collection and the URI doesn't end in "/", add a
            # Content-Location header.  This is needed even if we redirect such
            # requests (as above) in the event that this resource was created or
            # modified by the request.
            #
            if self.isCollection() and request.uri[-1:] != "/":
                response.headers.setHeader("content-location", request.uri + "/")

            return response

        return maybeDeferred(super(DAVResource, self).renderHTTP, request).addCallback(setHeaders)

class DAVLeafResource (DAVResource, LeafResource):
    """
    DAV resource with no children.
    """
    def findChildren(self, depth):
        return ()
