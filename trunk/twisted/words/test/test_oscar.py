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
