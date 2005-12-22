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
WebDAV MKCOL method
"""

__all__ = ["http_MKCOL"]

import os

from twisted.python import log
from twisted.python.filepath import FilePath
from twisted.python.failure import Failure
from twisted.web2 import responsecode
from twisted.web2.iweb import IRequest
from twisted.web2.http import StatusResponse
from twisted.web2.dav.fileop import mkcollection
from twisted.web2.dav.http import statusForFailure
from twisted.web2.dav.util import noDataFromStream

def http_MKCOL(self, request):
    """
    Respond to a MKCOL request. (RFC 2518, section 8.3)
    """
    self.fp.restat(False)

    if self.fp.exists():
        log.err("Attempt to create collection where file exists: %s"
                % (self.fp.path,))
        return responsecode.NOT_ALLOWED

    if not self.fp.parent().isdir():
        log.err("Attempt to create collection with no parent: %s"
                % (self.fp.path,))
        return StatusResponse(responsecode.CONFLICT, "No parent collection")

    #
    # Read request body
    #
    d = noDataFromStream(request.stream)

    #
    # Create directory
    #
    def gotNoData(_):
        return mkcollection(self.fp)

    def gotError(f):
        log.err("Error while handling MKCOL body: %s" % (f,))

        # ValueError is raised on a bad request.  Re-raise others.
        f.trap(ValueError)

        return responsecode.UNSUPPORTED_MEDIA_TYPE

    d.addCallback(gotNoData)
    d.addErrback(gotError)

    return d
