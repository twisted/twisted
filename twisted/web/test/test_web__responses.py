# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP responses.
"""

from twisted.trial import unittest
from twisted.web._responses import str2response

class Str2ResponseTests(unittest.TestCase):
    """
    Tests for L{str2response}.
    """

    def test_validCode(self):
        m = str2response("302")
        self.assertEqual(m, "Found")

    def test_invalidCode(self):
        m = str2response("987")
        self.assertEqual(m, None)

    def test_nonintegerCode(self):
        m = str2response("InvalidCode")
        self.assertEqual(m, None)
