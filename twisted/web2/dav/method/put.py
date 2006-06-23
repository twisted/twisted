# -*- test-case-name: twisted.web2.dav.test.test_put -*-
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
WebDAV PUT method
"""

__all__ = ["preconditions_PUT", "http_PUT"]

from twisted.python import log
from twisted.web2 import responsecode
from twisted.web2.http import HTTPError, StatusResponse
from twisted.web2.dav.fileop import put

def preconditions_PUT(self, request):
    if self.fp.exists():
        if not self.fp.isfile():
            log.err("Unable to PUT to non-file: %s" % (self.fp.path,))
            raise HTTPError(StatusResponse(
                responsecode.FORBIDDEN,
                "The requested resource exists but is not backed by a regular file."
            ))
        resource_is_new = False
    else:
        if not self.fp.parent().isdir():
            log.err("No such directory: %s" % (self.fp.path,))
            raise HTTPError(StatusResponse(
                responsecode.CONFLICT,
                "Parent collection resource does not exist."
            ))
        resource_is_new = True

    #
    # HTTP/1.1 (RFC 2068, section 9.6) requires that we respond with a Not
    # Implemented error if we get a Content-* header which we don't
    # recognize and handle properly.
    #
    for header, value in request.headers.getAllRawHeaders():
        if header.startswith("Content-") and header not in (
           #"Content-Base",     # Doesn't make sense in PUT?
           #"Content-Encoding", # Requires that we decode it?
            "Content-Language",
            "Content-Length",
           #"Content-Location", # Doesn't make sense in PUT?
            "Content-MD5",
           #"Content-Range",    # FIXME: Need to implement this
            "Content-Type",
        ):
            log.err("Client sent unrecognized content header in PUT request: %s"
                    % (header,))
            raise HTTPError(StatusResponse(
                responsecode.NOT_IMPLEMENTED,
                "Unrecognized content header %r in request." % (header,)
            ))

def http_PUT(self, request):
    """
    Respond to a PUT request. (RFC 2518, section 8.7)
    """
    log.msg("Writing request stream to %s" % (self.fp.path,))

    #
    # Don't pass in the request URI, since PUT isn't specified to be able
    # to return a MULTI_STATUS response, which is WebDAV-specific (and PUT is
    # not).
    #
    return put(request.stream, self.fp)
