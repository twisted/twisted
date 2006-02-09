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

import os

from twisted.python import log
from twisted.python.filepath import FilePath
from twisted.internet.defer import maybeDeferred
from twisted.web2 import responsecode
from twisted.web2.http import StatusResponse
from twisted.web2.dav.fileop import copy, delete, move

# FIXME: This is circular
import twisted.web2.dav.static

def http_COPY(self, request):
    """
    Respond to a COPY request. (RFC 2518, section 8.8)
    """
    r = prepareForCopy(self, request)
    if type(r) is int or isinstance(r, StatusResponse): return r
    destination, destination_uri, depth = r

    return copy(self.fp, destination.fp, destination_uri, depth)

def http_MOVE(self, request):
    """
    Respond to a MOVE request. (RFC 2518, section 8.9)
    """
    r = prepareForCopy(self, request)
    if type(r) is int or isinstance(r, StatusResponse): return r
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
        return StatusResponse(responsecode.BAD_REQUEST, msg)

    return move(self.fp, request.uri, destination.fp, destination_uri, depth)

def prepareForCopy(self, request):
    if not self.fp.exists():
        log.err("File not found: %s" % (self.fp.path,))
        return StatusResponse(
            responsecode.NOT_FOUND,
            "Source resource %s not found." % (request.uri,)
        )

    #
    # Find the destination resource
    #

    destination_uri = request.headers.getHeader("destination")

    if not destination_uri:
        msg = "No destination header in %s request." % (request.method,)
        log.err(msg)
        return StatusResponse(responsecode.BAD_REQUEST, msg)

    try:
        destination = self.locateSiblingResource(request, destination_uri)
    except ValueError, e:
        return StatusResponse(responsecode.BAD_GATEWAY, str(e))

    #
    # Destination must be a DAV resource
    #
    # FIXME: A better check would be for adaptability to an IDAVResource
    # interface; another reason why IDAVResource is probably a good idea.
    if not isinstance(destination, twisted.web2.dav.static.DAVFile):
        log.err("Attempt to %s to a non-DAV resource: (%s) %s"
                % (request.method, destination.__class__, destination_uri))
        return StatusResponse(
            responsecode.FORBIDDEN,
            "Destination %s is not a WebDAV resource." % (destination_uri,)
        )

    #
    # Check for existing destination resource
    #

    overwrite = request.headers.getHeader("overwrite", True)

    if destination.fp.exists() and not overwrite:
        log.err("Attempt to %s onto existing file without overwrite  flag enabled: %s"
                % (request.method, destination.fp.path))
        return StatusResponse(
            responsecode.PRECONDITION_FAILED,
            "Destination %s already exists." % (destination_uri,)
        )

    #
    # Make sure destination's parent exists
    #

    if not destination.fp.parent().isdir():
        log.err("Attempt to %s to a resource with no parent: %s"
                % (request.method, destination.fp.path))
        return StatusResponse(responsecode.CONFLICT, "No parent collection.")

    #
    # Get the depth
    #

    depth = request.headers.getHeader("depth", "infinity")

    if depth not in ("0", "infinity"):
        msg = ("Client sent illegal depth header value: %s" % (depth,))
        log.err(msg)
        return StatusResponse(responsecode.BAD_REQUEST, msg)

    return destination, destination_uri, depth
