# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""General tests for twisted.enterprise."""

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
            self.assertEquals(util.quote(value, typ), expected)
