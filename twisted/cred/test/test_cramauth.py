# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.cred.credentials.CramMD5Credentials}.
"""

class CramMD5CredentialsTests(unittest.TestCase):
    def testIdempotentChallenge(self):
        c = credentials.CramMD5Credentials()
        chal = c.getChallenge()
        self.assertEqual(chal, c.getChallenge())

    def testCheckPassword(self):
        c = credentials.CramMD5Credentials()
        chal = c.getChallenge()
        c.response = hexlify(hmac.HMAC(b'secret', chal).digest())
        self.assertTrue(c.checkPassword(b'secret'))

    def testWrongPassword(self):
        c = credentials.CramMD5Credentials()
        self.assertFalse(c.checkPassword(b'secret'))
