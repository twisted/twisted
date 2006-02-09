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

from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet.defer import succeed, maybeDeferred
from twisted.web2 import responsecode
from twisted.web2.static import File
from twisted.web2.iweb import IResponse
from twisted.web2.http import HTTPError, RedirectResponse
from twisted.web2.http_headers import ETag
from twisted.web2.dav import davxml
from twisted.web2.dav.util import bindMethods
from twisted.web2.dav.props import WebDAVPropertyStore as LivePropertyStore

try:
    from twisted.web2.dav.xattrprops import xattrPropertyStore as DeadPropertyStore
except ImportError:
    log.msg("No dead property store available; using nonePropertyStore.")
    log.msg("Setting of dead properties will not be allowed.")
    from twisted.web2.dav.noneprops import NonePropertyStore as DeadPropertyStore

#
# FIXME: We need an IDAVResource interface.
#  - isCollection()
#  - findChildren()
#  - hasProperty()
#  - readProperty()
#  - writeProperty()
#  - removeProperty()
# eg. see FIXME comment in findChildren()
#

#
# FIXME: How can we abstract out the file operations from the DAV logic?
# Inheriting file File ties us somewhat to a File-based backing store.
# What would be better is to have a DAVResource class with subclasses that
# implement different backing stores.
# DAVFile could then inherrit from both File and DAVResource.
#

class DAVFile (File):
    """
    WebDAV-accessible File resource.

    Extends twisted.web2.static.File to handle WebDAV methods.
    """
    davComplianceClasses = ("1",) # "2"

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
    # HTTP
    ##

    #
    # Preconditions
    #

    def checkIfMatch(self, request):
        """
        Check the If-Match header against the resource.
        Raise HTTPError if we shouldn't continue.
        (RFC 2616, section 14.24)
        """
        #
        # NOTE: RFC 2616 (HTTP) section 14.25, and 14.26 say:
        #   If the request would, without the If-Match header field, result in
        #   anything other than a 2xx status, then the If-Match header MUST be
        #   ignored.
        # This implies that we have to attempt the request, check the status,
        # and act on the If-Match header only if the request resulted in an
        # non-error status.  That seems rather expensive.  Furthermore, for many
        # operations, such as PUT, COPY, MOVE and DELETE, we'd have to back out
        # the successful operation first.  Ouch!
        #
        # Roy Fielding says that only likely errors which are detectable early
        # apply here, so no ouch is necessary.  Specifically: "You only need to
        # check things that are exposed via the HTTP interface, such as
        # authorization."  Sounds good.
        #
        match = request.headers.getHeader("if-match")
        if match:
            if match == ("*",):
                if not self.exists():
                    raise HTTPError(responsecode.PRECONDITION_FAILED)
            else:
                my_etag = self.etag()
                if my_etag is None:
                    raise HTTPError(responsecode.PRECONDITION_FAILED)
                for etag in match:
                    if etag.match(my_etag, True): break
                else:
                    raise HTTPError(responsecode.PRECONDITION_FAILED)

    def checkIfNoneMatch(self, request):
        """
        Check the If-None-Match header against the resource.
        Raise HTTPError if we shouldn't continue.
        (RFC 2616, section 14.26)
        """
        #
        # NOTE: See NOTE in checkIfMatch re: ignoring the header 
        #
        match = request.headers.getHeader("if-none-match")
        if match:
            if len(match) == 1 and match[0] == "*":
                if self.exists():
                    raise HTTPError(responsecode.PRECONDITION_FAILED)
            else:
                if request.method in ("GET", "HEAD"):
                    error = HTTPError(responsecode.NOT_MODIFIED)
                    #
                    # Don't use weak ETags in a Range request.  HTTP allows it,
                    # but it can produce a corrupt entity on the client side.
                    #
                    if request.headers.hasHeader("range"):
                        strong = True
                    else:
                        strong = False
                else:
                    error = HTTPError(responsecode.PRECONDITION_FAILED)
                    strong = True

                my_etag = self.etag()
                if my_etag is not None:
                    for etag in match:
                        if my_etag.match(ETag(etag), strongCompare=strong):
                            raise error

    def checkIfModifiedSince(self, request):
        """
        Check the If-Modified-Since header against the resource.
        Raise HTTPError if we shouldn't continue.
        (RFC 2616, section 14.25)
        """
        #
        # FIXME: Check the Range header.  See 14.35.  I don't understand
        # the implications of 14.35.2.
        #
        ims = request.headers.getHeader("if-modified-since")
        if ims:
            if ims < self.lastModified():
                raise HTTPError(responsecode.NOT_MODIFIED)

    def checkIfUnmodifiedSince(self, request):
        """
        Check the If-Unmodified-Since header against the resource.
        Raise HTTPError if we shouldn't continue.
        (RFC 2616, section 14.28)
        """
        ius = request.headers.getHeader("if-unmodified-since")
        if ius:
            if ius >= self.lastModified():
                raise HTTPError(responsecode.PRECONDITION_FAILED)

    def checkPreconditions(self, request):
        """
        Check preconditions on the request.
        """
        failure = None

        for test in (
            self.checkIfMatch,
            self.checkIfNoneMatch,
            self.checkIfModifiedSince,
            self.checkIfUnmodifiedSince,
        ):
            try:
                test(request)
            except HTTPError, e:
                #
                # RFC 2518, section 13.3.4: Don't respond with Not Modified
                # unless all four match/modified preconditions agree.
                #
                if e.response.code == responsecode.NOT_MODIFIED:
                    if failure is None: failure = Failure()
                else:
                    Failure().raiseException()

        if failure is not None: failure.raiseException()

    ##
    # WebDAV
    ##

    def contentType(self):
        # Allow dead property to override
        if (davxml.dav_namespace, "getcontenttype") in self.deadProperties:
            return self.deadProperties[(davxml.dav_namespace, "getcontenttype")]
        else:
            return super(DAVFile, self).contentType()

    def displayName(self):
        # Allow dead property to override
        if (davxml.dav_namespace, "displayname") in self.deadProperties:
            return self.deadProperties[(davxml.dav_namespace, "displayname")]
        else:
            return super(DAVFile, self).displayName()

    def isCollection(self):
        """
        Returns True if this resource is a collection resource, False otherwise.
        """
        for child in self.listChildren(): return True
        return self.fp.isdir()

    def findChildren(self, depth):
        """
        Returns a list of child resources for the given depth. (RFC 2518,
        section 9.2)
        Because resources do not know their request URIs, chidren are returned
        as tuples (resource, uri), where uri is a URL path relative to this
        resource and resource is the child resource.
        """
        #
        # I'd rather call this children(), but self.children is inherited from
        # File.  I'd call that static_children or something more specific.
        #
        assert depth in ("0", "1", "infinity"), "Invalid depth: %s" % (depth,)
        if depth != "0" and self.isCollection():
            for name in self.listChildren():
                child = self.getChild(name)
                if child:
                    #
                    # FIXME: This code breaks if we encounter a child that isn't
                    # a DAVFile (ie. has isCollection() and findChildren()). This
                    # may be an argument for an IDAVResource interface.
                    #
                    if child.isCollection():
                        yield (child, name + "/")
                        if depth == "infinity":
                            for grandchild in child.findChildren(depth):
                                yield (grandchild[0], name + "/" + grandchild[1])
                    else:
                        yield (child, name)

    properties     = property(LivePropertyStore)
    deadProperties = property(DeadPropertyStore)

    def hasProperty(self, property):
        """
        property is a davxml.WebDAVElement instance.
        Returns True if the given property is set.
        """
        return (property.qname() in self.properties)

    def readProperty(self, property):
        """
        property is a davxml.WebDAVElement instance.
        Returns the value of the given property.
        """
        try:
            return self.properties[property.qname()]
        except KeyError:
            log.err("No such property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)

    def writeProperty(self, property):
        """
        property is a davxml.WebDAVElement instance.
        Returns the value of the given property.
        """
        try:
            self.properties[property.qname()] = property
        except ValueError:
            log.err("Read-only property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)

    def removeProperty(self, property):
        """
        property is a davxml.WebDAVElement instance.
        Removes the given property.
        """
        try:
            del(self.properties[property.qname()])
        except ValueError:
            log.err("Read-only property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)
        except KeyError:
            log.err("No such property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)

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

        #
        # Generate response and append common headers
        #
        try:
            self.checkPreconditions(request)
        except HTTPError, e:
            response = succeed(e.response)
        else:
            response = maybeDeferred(super(DAVFile, self).renderHTTP, request)

        assert response, "No response"

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

        response.addCallback(setHeaders)
        return response

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
        while segments:
            sibling, segments = sibling.locateChild(request, segments)
        return sibling

    def createSimilarFile(self, path):
        return self.__class__(path, defaultType=self.defaultType, indexNames=self.indexNames[:])

#
# Attach method handlers to DAVFile
#

import twisted.web2.dav.method

bindMethods(twisted.web2.dav.method, DAVFile)
