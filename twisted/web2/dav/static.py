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

See RFC 2616: http://www.ietf.org/rfc/rfc2616.txt (HTTP)
See RFC 2518: http://www.ietf.org/rfc/rfc2518.txt (WebDAV)
See RFC 3253: http://www.ietf.org/rfc/rfc3253.txt (WebDAV + Versioning)
"""

__all__ = ["DAVFile"]

import os
import time
import urllib
import urlparse

from zope.interface import implements
from twisted.python import log
from twisted.internet.defer import maybeDeferred
from twisted.web2.static import File
from twisted.web2.iweb import IResponse
from twisted.web2.http import RedirectResponse
from twisted.web2.server import StopTraversal
from twisted.web2.dav.idav import IDAVResource
from twisted.web2.dav.resource import DAVPropertyMixIn
from twisted.web2.dav.util import bindMethods

try:
    from twisted.web2.dav.xattrprops import xattrPropertyStore as DeadPropertyStore
except ImportError:
    log.msg("No dead property store available; using nonePropertyStore.")
    log.msg("Setting of dead properties will not be allowed.")
    from twisted.web2.dav.noneprops import NonePropertyStore as DeadPropertyStore

#
# FIXME: How can we abstract out the file operations from the DAV logic?
# Inheriting file File ties us somewhat to a File-based backing store.
# What would be better is to have a DAVResource class with subclasses that
# implement different backing stores.
# DAVFile could then inherrit from both File and DAVResource.
#

class DAVFile (DAVPropertyMixIn, File):
    """
    WebDAV-accessible File resource.

    Extends twisted.web2.static.File to handle WebDAV methods.
    """
    implements(IDAVResource)

    davComplianceClasses = ("1",) # Add "2" when we have locking

    def __init__(self, path,
                 defaultType="text/plain",
                 indexNames=None):
        """
        Create a file with the given path.

        The defaultType and indexNames arguments are passed on to the File
        superclass.

        Does not accept the processors and ignoredExts arguments, unlike File.
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
        #
        # I'd rather call this children(), but self.children is inherited from
        # File.  I'd call that static_children or something more specific.
        #
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

    def getDeadProperties(self):
        if not hasattr(self, "_dead_properties"):
            self._dead_properties = DeadPropertyStore(self)
        return self._dead_properties

    ##
    # Render
    ##

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

            response.headers.setHeader("dav", self.davComplianceClasses)

            #
            # If this is a collection and the URI doesn't end in "/", add a
            # Content-Location header.  This is needed even if we redirect such
            # requests (as above) in the event that this resource was created or
            # modified by the request.
            #
            if self.isCollection() and request.uri[-1:] != "/":
                response.headers.setHeader("content-location", request.uri + "/")

            return response

        return maybeDeferred(super(DAVFile, self).renderHTTP, request).addCallback(setHeaders)

    ##
    # Workarounds for issues with File
    ##

    def ignoreExt(self, ext):
        """
        Does nothing; doesn't apply to this subclass.
        """
        pass

    def locateSiblingResource(self, request, uri):
        """
        Look up a resource on the same server with the given URI.
        """
        if uri is None: return None

        #
        # Parse the URI
        #
    
        (scheme, host, path, params, querystring, fragment) = urlparse.urlparse(uri, "http")
    
        # Request hostname and destination hostname have to be the same.
        if host and host != request.headers.getHeader("host"):
            raise ValueError("URI is not on this site (%s): %s" % (request.headers.getHeader("host"), uri))
    
        segments = path.split("/")
        if segments[0]:
            raise AssertionError("URI path didn't begin with '/': %s" % (path,))
        segments = segments[1:]
    
        #
        # Find the resource with the given path.
        #
    
        #
        # FIXME: site isn't in the IRequest interface, and there needs to be an
        # ISite interface.
        #
        # FIXME: How do I get params, querystring, and fragment passed down to
        # the new resource?  Insert them to segments?
        #
        sibling = request.site.resource
        while segments and segments is not StopTraversal:        
            sibling, segments = sibling.locateChild(request, segments)
        return sibling

    def createSimilarFile(self, path):
        return self.__class__(path, defaultType=self.defaultType, indexNames=self.indexNames[:])

#
# Attach method handlers to DAVFile
#

import twisted.web2.dav.method

bindMethods(twisted.web2.dav.method, DAVFile)
