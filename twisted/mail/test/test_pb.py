# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{twisted.mail.pb} is a deprecated module. This test just verifies that
the deprecation warning is triggered correctly.
"""

from twisted.trial import unittest

from twisted import mail

class ModuleDeprecatedTest(unittest.TestCase):
    """
    Tests that the L{twisted.mail.pb} module is deprecated.
    """

    def test_deprecation(self):
        """
        Tests that a DeprecationWarning is signalled if the 
        L{mail.twisted.pb} module is loaded.
        """

        import twisted.mail.pb 
        warningsShown = self.flushWarnings([self.test_deprecation])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            "twisted.mail.pb was deprecated in Twisted 13.2.0: "
            "Please use a real mail protocol, e.g., imap or pop.")
