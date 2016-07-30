# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.protocols.oscar}.
"""

from twisted.trial.unittest import TestCase

from twisted.words.protocols.oscar import encryptPasswordMD5


class PasswordTests(TestCase):
    """
    Tests for L{encryptPasswordMD5}.
    """
    def test_encryptPasswordMD5(self):
        """
        L{encryptPasswordMD5} hashes the given password and key and returns a
        string suitable to use to authenticate against an OSCAR server.
        """
        self.assertEqual(
            encryptPasswordMD5('foo', 'bar').encode('hex'),
            'd73475c370a7b18c6c20386bcf1339f2')



class OscarDeprecationTests(TestCase):
    """
    Tests for the deprecation of L{twisted.words.protocols.oscar}.
    """
    def test_deprecated(self):
        """
        L{twisted.words.protocols.oscar} is deprecated.
        """
        from twisted.words import protocols
        protocols.oscar

        warnings = self.flushWarnings([self.test_deprecated])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["message"], (
            "twisted.words.protocols.oscar was deprecated in Twisted 16.2.0: "
            "There is no replacement for this module."))
