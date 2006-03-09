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
WebDAV support for Twisted Web2.

See RFC 2616: http://www.ietf.org/rfc/rfc2616.txt (HTTP)
See RFC 2518: http://www.ietf.org/rfc/rfc2518.txt (WebDAV)
See RFC 3253: http://www.ietf.org/rfc/rfc3253.txt (WebDAV Versioning Extentions)
See RFC 3744: http://www.ietf.org/rfc/rfc3744.txt (WebDAV Access Control Protocol)

See also: http://skrb.org/ietf/http_errata.html (Errata to RFC 2616)
"""

__version__ = 'SVN-Trunk'
version = __version__

__all__ = [ 
    "acl",
    "fileop",
    "davxml",
    "http",
    "idav",
    "noneprops",
    "resource",
    "static",
    "util",
    "xattrprops",
]
