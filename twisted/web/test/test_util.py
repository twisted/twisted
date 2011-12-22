# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.util}.
"""

from twisted.trial.unittest import TestCase
from twisted.web.util import _hasSubstring, redirectTo

from twisted.web.http import FOUND
from twisted.web.server import Request

from twisted.web.test.test_web import DummyChannel

class HasSubstringTestCase(TestCase):
    """
    Test regular expression-based substring searching.
    """

    def test_hasSubstring(self):
        """
        L{_hasSubstring} returns True if the specified substring is present in
        the text being searched.
        """
        self.assertTrue(_hasSubstring("foo", "<foo>"))

    def test_hasSubstringWithoutMatch(self):
        """
        L{_hasSubstring} returns False if the specified substring is not
        present in the text being searched.
        """
        self.assertFalse(_hasSubstring("foo", "<bar>"))

    def test_hasSubstringOnlyMatchesStringsWithNonAlphnumericNeighbors(self):
        """
        L{_hasSubstring} returns False if the specified substring is present
        in the text being searched but the characters surrounding the
        substring are alphanumeric.
        """
        self.assertFalse(_hasSubstring("foo", "barfoobaz"))
        self.assertFalse(_hasSubstring("foo", "1foo2"))

    def test_hasSubstringEscapesKey(self):
        """
        L{_hasSubstring} uses a regular expression to determine if a substring
        exists in a text snippet.  The substring is escaped to ensure that it
        doesn't interfere with the regular expression.
        """
        self.assertTrue(_hasSubstring("[b-a]",
                                      "Python can generate names like [b-a]."))


class RedirectToTestCase(TestCase):
    """
    Tests for L{redirectTo}.
    """

    def test_headersAndCode(self):
        """
        L{redirectTo} will set the C{Location} and C{Content-Type} headers on
        its request, and set the response code to C{FOUND}, so the browser will
        be redirected.
        """
        request = Request(DummyChannel(), True)
        request.method = 'GET'
        targetURL = "http://target.example.com/4321"
        redirectTo(targetURL, request)
        self.assertEqual(request.code, FOUND)
        self.assertEqual(
            request.responseHeaders.getRawHeaders('location'), [targetURL])
        self.assertEqual(
            request.responseHeaders.getRawHeaders('content-type'),
            ['text/html; charset=utf-8'])

    def test_redirectToUnicodeURL(self) :
        """
        L{redirectTo} will raise TypeError if unicode object is passed in URL
        """  
        request = Request(DummyChannel(), True)
        request.method = 'GET'
        targetURL = u'http://target.example.com/4321'
        self.assertRaises(TypeError, redirectTo, targetURL, request) 
