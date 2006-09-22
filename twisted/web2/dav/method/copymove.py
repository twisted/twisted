# -*- test-case-name: twisted.web2.dav.test.test_copy,twisted.web2.dav.test.test_move -*-
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
WebDAV COPY and MOVE methods.
"""

__all__ = ["http_COPY", "http_MOVE"]

from twisted.python import log
from twisted.web2 import responsecode
from twisted.web2.http import HTTPError, StatusResponse
from twisted.web2.filter.location import addLocation
from twisted.web2.dav.idav import IDAVResource
from twisted.web2.dav.fileop import copy, move

# FIXME: This is circular
import twisted.web2.dav.static

def http_COPY(self, request):
    """
    Respond to a COPY request. (RFC 2518, section 8.8)
    """
    def doCopy(r):
        destination, destination_uri, depth = r

        # May need to add a location header
        addLocation(request, destination_uri)

        return copy(self.fp, destination.fp, destination_uri, depth)

    d = prepareForCopy(self, request)
    d.addCallback(doCopy)
    return d

def http_MOVE(self, request):
    """
    Respond to a MOVE request. (RFC 2518, section 8.9)
    """
    def doMove(r):
        destination, destination_uri, depth = r

        #
        # RFC 2518, section 8.9 says that we must act as if the Depth header is set
        # to infinity, and that the client must omit the Depth header or set it to
        # infinity.
        #
        # This seems somewhat at odds with the notion that a bad request should be
        # rejected outright; if the client sends a bad depth header, the client is
        # broken, and section 8 suggests that a bad request should be rejected...
        #
        # Let's play it safe for now and ignore broken clients.
        #
        if self.fp.isdir() and depth != "infinity":
            msg = "Client sent illegal depth header value for MOVE: %s" % (depth,)
            log.err(msg)
            raise HTTPError(StatusResponse(responsecode.BAD_REQUEST, msg))

        # May need to add a location header
        addLocation(request, destination_uri)

        return move(self.fp, request.uri, destination.fp, destination_uri, depth)

    d = prepareForCopy(self, request)
    d.addCallback(doMove)
    return d

def prepareForCopy(self, request):
    #
    # Get the depth
    #

    depth = request.headers.getHeader("depth", "infinity")

    if depth not in ("0", "infinity"):
        msg = ("Client sent illegal depth header value: %s" % (depth,))
        log.err(msg)
        raise HTTPError(StatusResponse(responsecode.BAD_REQUEST, msg))

    #
    # Verify this resource exists
    #

    if not self.exists():
        log.err("File not found: %s" % (self.fp.path,))
        raise HTTPError(StatusResponse(
            responsecode.NOT_FOUND,
            "Source resource %s not found." % (request.uri,)
        ))

    #
    # Get the destination
    #

    destination_uri = request.headers.getHeader("destination")

    if not destination_uri:
        msg = "No destination header in %s request." % (request.method,)
        log.err(msg)
        raise HTTPError(StatusResponse(responsecode.BAD_REQUEST, msg))

    d = request.locateResource(destination_uri)
    d.addCallback(_prepareForCopy, destination_uri, request, depth)

    return d

def _prepareForCopy(destination, destination_uri, request, depth):
    #
    # Destination must be a DAV resource
    #

    try:
        destination = IDAVResource(destination)
    except TypeError:
        log.err("Attempt to %s to a non-DAV resource: (%s) %s"
                % (request.method, destination.__class__, destination_uri))
        raise HTTPError(StatusResponse(
            responsecode.FORBIDDEN,
            "Destination %s is not a WebDAV resource." % (destination_uri,)
        ))

    #
    # FIXME: Right now we don't know how to copy to a non-DAVFile resource.
    # We may need some more API in IDAVResource.
    # So far, we need: .exists(), .fp.parent()
    #

    if not isinstance(destination, twisted.web2.dav.static.DAVFile):
        log.err("DAV copy between non-DAVFile DAV resources isn't implemented")
        raise HTTPError(StatusResponse(
            responsecode.NOT_IMPLEMENTED,
            "Destination %s is not a DAVFile resource." % (destination_uri,)
        ))

    #
    # Check for existing destination resource
    #

    overwrite = request.headers.getHeader("overwrite", True)

    if destination.exists() and not overwrite:
        log.err("Attempt to %s onto existing file without overwrite flag enabled: %s"
                % (request.method, destination.fp.path))
        raise HTTPError(StatusResponse(
            responsecode.PRECONDITION_FAILED,
            "Destination %s already exists." % (destination_uri,)
        ))

    #
    # Make sure destination's parent exists
    #

    if not destination.fp.parent().isdir():
        log.err("Attempt to %s to a resource with no parent: %s"
                % (request.method, destination.fp.path))
        raise HTTPError(StatusResponse(responsecode.CONFLICT, "No parent collection."))

    return destination, destination_uri, depth
