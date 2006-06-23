# -*- test-case-name: twisted.web2.dav.test.test_delete -*-
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
WebDAV DELETE method
"""

__all__ = ["http_DELETE"]

from twisted.python import log
from twisted.web2 import responsecode
from twisted.web2.http import HTTPError
from twisted.web2.dav.fileop import delete

def http_DELETE(self, request):
    """
    Respond to a DELETE request. (RFC 2518, section 8.6)
    """
    if not self.fp.exists():
        log.err("File not found: %s" % (self.fp.path,))
        raise HTTPError(responsecode.NOT_FOUND)

    depth = request.headers.getHeader("depth", "infinity")

    return delete(request.uri, self.fp, depth)
