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

import os

from twisted.web2.dav.util import *

import twisted.web2.dav.test.util

class Utilities(twisted.web2.dav.test.util.TestCase):
    """
    Utilities.
    """
    def test_normalizeURL(self):
        self.assertEquals(normalizeURL("http://server//foo"), "http://server/foo")
        self.assertEquals(normalizeURL("http://server/foo/.."), "http://server/")
        self.assertEquals(normalizeURL("/foo/bar/..//"), "/foo")
        self.assertEquals(normalizeURL("//foo///bar/../baz"), "/foo/baz")
        self.assertEquals(normalizeURL("///../"), "/")
        self.assertEquals(normalizeURL("/.."), "/")

    def test_joinURL(self):
        self.assertEquals(joinURL("http://server/foo/"), "http://server/foo/")
        self.assertEquals(joinURL("http://server/foo", "/bar"), "http://server/foo/bar")
        self.assertEquals(joinURL("http://server/foo", "bar"), "http://server/foo/bar")
        self.assertEquals(joinURL("http://server/foo/", "/bar"), "http://server/foo/bar")
        self.assertEquals(joinURL("http://server/foo/", "/bar/.."), "http://server/foo")
        self.assertEquals(joinURL("http://server/foo/", "/bar/../"), "http://server/foo/")
        self.assertEquals(joinURL("http://server/foo/../", "/bar"), "http://server/bar")
        self.assertEquals(joinURL("/foo/"), "/foo/")
        self.assertEquals(joinURL("/foo", "/bar"), "/foo/bar")
        self.assertEquals(joinURL("/foo", "bar"), "/foo/bar")
        self.assertEquals(joinURL("/foo/", "/bar"), "/foo/bar")
        self.assertEquals(joinURL("/foo/", "/bar/.."), "/foo")
        self.assertEquals(joinURL("/foo/", "/bar/../"), "/foo/")
        self.assertEquals(joinURL("/foo/../", "/bar"), "/bar")
        self.assertEquals(joinURL("/foo", "/../"), "/")
