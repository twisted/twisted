# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.urlpath}.
"""

from twisted.trial import unittest
from twisted.python import urlpath


class URLPathTests(unittest.TestCase):
    def setUp(self):
        self.path = urlpath.URLPath.fromString("http://example.com/foo/bar?yes=no&no=yes#footer")

    def testStringConversion(self):
        self.assertEqual(str(self.path), "http://example.com/foo/bar?yes=no&no=yes#footer")

    def testChildString(self):
        self.assertEqual(str(self.path.child('hello')), "http://example.com/foo/bar/hello")
        self.assertEqual(str(self.path.child('hello').child('')), "http://example.com/foo/bar/hello/")

    def testSiblingString(self):
        self.assertEqual(str(self.path.sibling('baz')), 'http://example.com/foo/baz')

        # The sibling of http://example.com/foo/bar/
        #     is http://example.comf/foo/bar/baz
        # because really we are constructing a sibling of
        # http://example.com/foo/bar/index.html
        self.assertEqual(str(self.path.child('').sibling('baz')), 'http://example.com/foo/bar/baz')

    def testParentString(self):
        # parent should be equivalent to '..'
        # 'foo' is the current directory, '/' is the parent directory
        self.assertEqual(str(self.path.parent()), 'http://example.com/')
        self.assertEqual(str(self.path.child('').parent()), 'http://example.com/foo/')
        self.assertEqual(str(self.path.child('baz').parent()), 'http://example.com/foo/')
        self.assertEqual(str(self.path.parent().parent().parent().parent().parent()), 'http://example.com/')

    def testHereString(self):
        # here should be equivalent to '.'
        self.assertEqual(str(self.path.here()), 'http://example.com/foo/')
        self.assertEqual(str(self.path.child('').here()), 'http://example.com/foo/bar/')

