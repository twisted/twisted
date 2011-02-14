# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
General tests for twisted.enterprise.
"""

from twisted.trial import unittest

from twisted.enterprise import util

class QuotingTestCase(unittest.TestCase):

    def testQuoting(self):
        for value, typ, expected in [
            (12, "integer", "12"),
            ("foo'd", "text", "'foo''d'"),
            ("\x00abc\\s\xFF", "bytea", "'\\\\000abc\\\\\\\\s\\377'"),
            (12, "text", "'12'"),
            (u"123'456", "text", u"'123''456'")
            ]:
            self.assertEquals(
                self.callDeprecated(util._deprecatedVersion, util.quote, value,
                                    typ),
                expected)


    def test_safeDeprecation(self):
        """
        L{safe} is deprecated.
        """
        self.callDeprecated(util._deprecatedVersion, util.safe, "foo")


    def test_getKeyColumnDeprecation(self):
        """
        L{getKeyColumn} is deprecated.
        """
        class Row(object):
            rowKeyColumns = ()
        self.callDeprecated(util._deprecatedVersion, util.getKeyColumn, Row, "foo")
