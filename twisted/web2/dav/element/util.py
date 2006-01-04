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
WebDAV XML utilities.

This module provides XML utilities for use with WebDAV.

See RFC 2518: http://www.ietf.org/rfc/rfc2518.txt (WebDAV)
"""

__all__ = [
    "PrintXML",
    "encodeXMLName",
    "decodeXMLName",
]

try:
    import xml.dom.ext as ext
except ImportError:
    import twisted.web2.dav.element.xmlext as ext

def PrintXML(document, stream):
    document.normalize()
    ext.Print(document, stream)
    # For debugging, this is easier to read: (FIXME: disable for normal use)
    #ext.PrettyPrint(document, stream)

def encodeXMLName(name):
    """
    Encodes an XML (namespace, localname) pair into an ASCII string.
    If namespace is None, returns localname encoded as UTF-8.
    Otherwise, returns {namespace}localname encoded as UTF-8.
    """
    namespace, name = name
    if namespace is None: return name.encode("utf-8")
    return (u"{%s}%s" % (namespace, name)).encode("utf-8")

def decodeXMLName(name):
    """
    Decodes an XML (namespace, localname) pair from an ASCII string as encoded
    by encodeXMLName().
    """
    if name[0] is not "{": return (None, name.decode("utf-8"))

    index = name.find("}")

    if (index is -1 or not len(name) > index):
        raise ValueError("Invalid encoded name: %r" % (name,))

    return (name[1:index].decode("utf-8"), name[index+1:].decode("utf-8"))
