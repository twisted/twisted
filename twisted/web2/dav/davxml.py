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
WebDAV XML Support.

This module provides XML utilities for use with WebDAV.

This API is considered private to static.py and is therefore subject to
change.

See RFC 2518: http://www.ietf.org/rfc/rfc2518.txt (WebDAV)
See RFC 3253: http://www.ietf.org/rfc/rfc3253.txt (WebDAV + Versioning)
See RFC 3744: http://www.ietf.org/rfc/rfc3744.txt (WebDAV ACLs)
"""

from twisted.web2.dav.element.parser import registerElements, WebDAVDocument, lookupElement
from twisted.web2.dav.element.util import encodeXMLName, decodeXMLName

#
# Import all XML element definitions
#

from twisted.web2.dav.element.base    import *
from twisted.web2.dav.element.rfc2518 import *
from twisted.web2.dav.element.rfc3253 import *
from twisted.web2.dav.element.rfc3744 import *

#
# Register all XML elements with the parser
#

import twisted.web2.dav.element.base
import twisted.web2.dav.element.rfc2518
import twisted.web2.dav.element.rfc3253
import twisted.web2.dav.element.rfc3744

__all__ = (
    registerElements(twisted.web2.dav.element.base   ) +
    registerElements(twisted.web2.dav.element.rfc2518) +
    registerElements(twisted.web2.dav.element.rfc3253) +
    registerElements(twisted.web2.dav.element.rfc3744) +
    ["registerElements", "WebDAVDocument", "lookupElement", "encodeXMLName", "decodeXMLName"]
)
