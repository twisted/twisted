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
DAV Property store using file system extended attributes.

This API is considered private to static.py and is therefore subject to
change.
"""

__all__ = ["xattrPropertyStore"]

import os
import urllib
import StringIO
import xattr
import UserDict

from twisted.python import log

from twisted.web2.dav import davxml

class xattrPropertyStore (object, UserDict.DictMixin):
    """
    This implementation uses Bob Ippolito's xattr package.
    Note that the Bob's xattr package is Darwin specific, at least presently.
    """
    #
    # Dead properties are stored as extended attributes on disk.  In order to
    # avoid conflicts with other attributes, prefix dead property names.
    #
    dead_property_xattr_prefix = "WebDAV:"

    def _encode(clazz, name):
        #
        # FIXME: The xattr API in Mac OS 10.4.2 breaks if you have "/" in an
        # attribute name (radar://4202440). We'll quote the strings to get rid
        # of "/" characters for now.
        #
        result = list("{%s}%s" % name)
        for i in range(len(result)):
            c = result[i]
            if c in "%/": result[i] = "%%%02X" % (ord(c),)
        r = clazz.dead_property_xattr_prefix + ''.join(result)
        return r

    def _decode(clazz, name):
        name = urllib.unquote(name[len(clazz.dead_property_xattr_prefix):])

        index = name.find("}")
    
        if (index is -1 or not len(name) > index or not name[0] == "{"):
            raise ValueError("Invalid encoded name: %r" % (name,))
    
        return (name[1:index], name[index+1:])

    _encode = classmethod(_encode)
    _decode = classmethod(_decode)

    def __init__(self, resource):
        self.resource = resource
        self.attrs = xattr.xattr(self.resource.fp.path)

    def __getitem__(self, key):
        value = self.attrs[self._encode(key)]
        doc = davxml.WebDAVDocument.fromString(value)

        return doc.root_element

    def __setitem__(self, key, value):
        output = StringIO.StringIO()
        value.writeXML(output)
        value = output.getvalue()
        output.close()

        log.msg("Writing property %r on file %s"
                % (key, self.resource.fp.path))

        self.attrs[self._encode(key)] = value

    def __delitem__(self, key):
        log.msg("Deleting property %r on file %s"
                % (key, self.resource.fp.path))

        del(self.attrs[self._encode(key)])

    def __contains__(self, key):
        try:
            return self._encode(key) in self.attrs
        except TypeError:
            return False

    def __iter__(self):
        prefix     = self.dead_property_xattr_prefix
        prefix_len = len(prefix)

        for key in self.attrs:
            if key.startswith(prefix):
                yield self._decode(key)
            else:
                # FIXME: What to do with non-DAV xattrs?
                pass

    def keys(self):
        prefix     = self.dead_property_xattr_prefix
        prefix_len = len(prefix)

        return [ self._decode(key) for key in self.attrs if key.startswith(prefix) ]
