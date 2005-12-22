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
Empty DAV property store.

This API is considered private to static.py and is therefore subject to
change.
"""

__all__ = ["NonePropertyStore"]

import UserDict

from twisted.web2.dav import davxml

class NonePropertyStore (object, UserDict.DictMixin):
    """
    DAV property store which contains no properties and does not allow
    properties to be set.
    """
    def __init__(self, resource):
        self.resource = resource

    def __getitem__(self, key):
        raise KeyError(key)

    def __setitem__(self, key, value):
        # Raise a permission denied error here, which will show up as a
        # FORBIDDEN response to the client.
        raise IOError(errno.EACCES, "permission denied for property %r on resource %s" % (key, self.resource))

    def __delitem__(self, key):
        raise KeyError(key)

    def __contains__(self, key):
        return False

    def __iter__(self):
        return iter(())

    def keys(self):
        return ()
