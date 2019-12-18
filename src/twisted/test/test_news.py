# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.news}.
"""

from twisted.trial.unittest import SynchronousTestCase
from twisted.python.compat import _PY3


class NewsDeprecationTestCase(SynchronousTestCase):
    """
    Tests for the deprecation of L{twisted.news}.
    """
    def test_deprecated3(self):
        """
        L{twisted.news} is deprecated on Python 3.
        """
        import twisted.news
        twisted.news
        warningsShown = self.flushWarnings([self.test_deprecated3])
        self.assertEqual(len(warningsShown), 1)
        self.assertIs(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            'twisted.news was deprecated in Twisted NEXT:'
            ' Will not be ported to Python 3.')


    def test_deprecated2(self):
        """
        L{twisted.news} is NOT deprecated on Python 2.
        """
        import twisted.news
        twisted.news
        warningsShown = self.flushWarnings([self.test_deprecated2])
        self.assertEqual(len(warningsShown), 0)


    if _PY3:
        test_deprecated2.skip = "Not relevant on Python 3."
    else:
        test_deprecated3.skip = "Not relevant on Python 2."
