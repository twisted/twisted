# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.util}.
"""

from twisted.trial.unittest import TestCase
from twisted.web.util import _hasSubstring



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
