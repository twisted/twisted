# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.conch.error package.
"""

from twisted.trial import unittest
from twisted.conch.error import ConchError

class ConchErrorTestCase(unittest.TestCase):
    """
    Test cases for L{twisted.conch.error.ConchError}.
    """
    def test_conchErrorDeprecation(self):
        """
        L{twisted.conch.error.ConchError} is deprecated in favor of
        L{twisted.conch.error.GeneralConchError}.
        """
        c = ConchError("foo")
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_conchErrorDeprecation])

        self.assertEqual(len(warnings), 1)
        self.assertEqual(
            warnings[0]["message"],
            "twisted.conch.error.ConchError is deprecated since Twisted 10.0. "
            "See twisted.conch.error.GeneralConchError.")
        self.assertEqual(
            warnings[0]['category'],
            DeprecationWarning)
