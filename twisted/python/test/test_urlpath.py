# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Tests for L{twisted.python.urlpath}.
"""

from twisted.trial import unittest
from twisted.python.urlpath import URLPath



class URLPathTestCase(unittest.TestCase):


    def setUp(self):
        url = "http://example.com/foo/bar?yes=no&no=yes#footer"
        self.path = URLPath.fromString(url)


    def test_stringConversion(self):
        self.assertEqual(str(self.path),
                         "http://example.com/foo/bar?yes=no&no=yes#footer")


    def test_childString(self):
        self.assertEqual(str(self.path.child('hello')),
                         "http://example.com/foo/bar/hello")
        self.assertEqual(str(self.path.child('hello').child('')),
                         "http://example.com/foo/bar/hello/")


    def test_siblingString(self):
        """
        The sibling of http://example.com/foo/bar/
            is http://example.comf/foo/bar/baz
        because really we are constructing a sibling of
        http://example.com/foo/bar/index.html
        """
        self.assertEqual(str(self.path.sibling('baz')),
                         'http://example.com/foo/baz')
        self.assertEqual(str(self.path.child('').sibling('baz')),
                         'http://example.com/foo/bar/baz')


    def test_parentString(self):
        """
        parent should be equivalent to '..'
        'foo' is the current directory, '/' is the parent directory
        """
        self.assertEqual(str(self.path.parent()), 'http://example.com/')
        self.assertEqual(str(self.path.child('').parent()),
                         'http://example.com/foo/')
        self.assertEqual(str(self.path.child('baz').parent()),
                         'http://example.com/foo/')
        self.assertEqual(str(self.path.parent().parent().parent()
                             .parent().parent()), 'http://example.com/')


    def test_hereString(self):
        """
        here should be equivalent to '.'
        """
        self.assertEqual(str(self.path.here()), 'http://example.com/foo/')
        self.assertEqual(str(self.path.child('').here()),
                         'http://example.com/foo/bar/')


    def test_clone(self):
        """
        L{clone<URLPath.clone>} should return a copy of the current path.
        """
        self.assertEqual(str(self.path.clone()),
                         'http://example.com/foo/bar?yes=no&no=yes#footer')


    def test_cloneNoQuery(self):
        """
        L{clone<URLPath.clone>} with C{keepQuery=False} should return a clone
        lacking the query parameters.
        """
        self.assertEqual(str(self.path.clone(keepQuery=False)),
                         'http://example.com/foo/bar#footer')


    def test_cloneNoFragment(self):
        """
        L{clone<URLPath.clone>} with C{keepFragment=False} should return a
        clone lacking the fragment.
        """
        self.assertEqual(str(self.path.clone(keepFragment=False)),
                         'http://example.com/foo/bar?yes=no&no=yes')



    def test_up(self):
        """
        L{up<URLPath.up>} should return a new L{URLPath} with the last segment
        removed and without the trailing slash.
        """
        self.assertEqual(str(self.path.child('foo').up()),
                         str(self.path.clone(keepQuery=False,
                                             keepFragment=False)),
                         "child(...).up() should be identical to the original "
                         "path but without the query or fragment")
        self.assertEqual(str(self.path.up().up().up().up()),
                         'http://example.com/')

        path = URLPath.fromString('http://example.com/foo/')
        self.assertEqual(str(path.up()), 'http://example.com/foo')


