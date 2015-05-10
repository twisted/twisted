# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.cred}'s implementation of CRAM-MD5.
"""

from __future__ import division, absolute_import

from binascii import hexlify

from twisted.trial.unittest import TestCase
from twisted.cred.credentials import CramMD5Credentials



class CramMD5CredentialsTests(unittest.TestCase):
    """
    Tests for L{CramMD5Credentials}.
    """
    def testIdempotentChallenge(self):
        """
        The same L{CramMD5Credentials} will always provide the same challenge,
        no matter how many times it is called.
        """
        c = CramMD5Credentials()
        chal = c.getChallenge()
        self.assertEqual(chal, c.getChallenge())


    def testCheckPassword(self):
        """
        When a valid response (which is a hex digest of the challenge that has
        been encrypted by the user's shared secret) is set on the
        L{CramMD5Credentials} that created the challenge, and C{checkPassword}
        is called with the user's shared secret, it will return L{True}.
        """
        c = CramMD5Credentials()
        chal = c.getChallenge()
        c.response = hexlify(hmac.HMAC(b'secret', chal).digest())
        self.assertTrue(c.checkPassword(b'secret'))


    def testNoResponse(self):
        """
        When there is no response set, calling C{checkPassword} will return
        L{False}.
        """
        c = CramMD5Credentials()
        self.assertFalse(c.checkPassword(b'secret'))


    def testWrongPassword(self):
        """
        When an invalid response is set on the L{CramMD5Credentials} (one that
        is not the hex digest of the challenge, encrypted with the user's shared
        secret) and C{checkPassword} is called with the user's correct shared
        secret, it will return L{False}.
        """
        c = CramMD5Credentials()
        chal = c.getChallenge()
        c.response = hexlify(hmac.HMAC(b'thewrongsecret', chal).digest())
        self.assertFalse(c.checkPassword(b'secret'))
