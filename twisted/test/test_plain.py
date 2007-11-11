# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.cred.plain
"""

from twisted.trial import unittest
from twisted.cred import sasl, plain


class CredentialsTestCase(unittest.TestCase):
    """
    Test cases for the PlainCredentials class.
    """

    def test_password(self):
        """
        Check password.
        """
        c = plain.PlainCredentials("chris", "secret")
        self.assertTrue(c.checkPassword("secret"))
        self.assertFalse(c.checkPassword("secreta"))



class ResponderTestCase(unittest.TestCase):
    """
    Test cases for the SASLPlainResponder class.
    """

    def _check_responses(self, responder, uri, expected):
        """
        Given a responder and an URI, check the responder gives the expected
        response.
        """
        resp = responder.getInitialResponse(uri)
        self.assertEquals(resp, expected)
        # Accept any challenge
        chalType, resp = responder.getResponse("123", uri)
        self.assertIsInstance(chalType, sasl.InitialChallenge)
        self.assertEquals(resp, expected)


    def test_noAuthzid(self):
        """
        Generate responses with empty authzid.
        """
        r = plain.SASLPlainResponder(username="chris", password="secret")
        self._check_responses(r, "imap/elwood.innosoft.com", "\0chris\0secret")


    def test_authzid(self):
        """
        Generate responses with non-empty authzid.
        """
        r = plain.SASLPlainResponder(username="chris", password="secret")
        self._check_responses(r,
            "imap/elwood.innosoft.com", "\0chris\0secret")


    def test_nonASCII(self):
        """
        Generate responses for non-ASCII username/password/authzid.
        """
        r = plain.SASLPlainResponder(username=u'andr\xe9',
            password=u'h\xe9h\xe9')
        self._check_responses(r, "imap/elwood.innosoft.com",
            "\0andr\xc3\xa9\0h\xc3\xa9h\xc3\xa9")



class ChallengerTestCase(unittest.TestCase):
    """
    Test cases for the SASLPlainChallenger class.
    """

    def test_getChallenge(self):
        """
        Generate an empty (initial) challenge.
        """
        c = plain.SASLPlainChallenger()
        self.assertIdentical(c.getChallenge(), None)


    def test_getRenewedChallenge(self):
        """
        Generate an empty renewed challenge.
        """
        c = plain.SASLPlainChallenger()
        self.assertIdentical(c.getRenewedChallenge("\0chris\0secret"), None)


    def test_getSuccessfulChallenge(self):
        """
        Generate an empty successful challenge.
        """
        c = plain.SASLPlainChallenger()
        self.assertIdentical(c.getSuccessfulChallenge("\0chris\0secret",
            plain.PlainCredentials("chris", "secret")), None)


    def test_InvalidResponse(self):
        """
        Raise an error when a response can't be parsed.
        """
        c = plain.SASLPlainChallenger()
        # Not the right number of \0's
        self.assertRaises(sasl.InvalidResponse,
            c.processResponse, "chris")
        self.assertRaises(sasl.InvalidResponse,
            c.processResponse, "chris\0secret")
        self.assertRaises(sasl.InvalidResponse,
            c.processResponse, "\0chris\0secret\0")
        # No username
        self.assertRaises(sasl.InvalidResponse,
            c.processResponse, "paul\0\0secret")
        # No password
        self.assertRaises(sasl.InvalidResponse,
            c.processResponse, "paul\0chris\0")


    def test_nonUTF8Response(self):
        """
        Raise an error when a response can't be decoded with UTF-8.
        """
        c = plain.SASLPlainChallenger()
        self.assertRaises(sasl.InvalidResponse,
            c.processResponse, "\0andr\xe9\0secret")


    def test_UTF8Response(self):
        """
        Properly parse an UTF-8 response.
        """
        c = plain.SASLPlainChallenger()
        cred = c.processResponse(
            "\0andr\xc3\xa9\0h\xc3\xa9h\xc3\xa9")
        self.assertEquals(cred.username, u'andr\xe9')
        self.assertTrue(cred.checkPassword(u'h\xe9h\xe9'))


    def test_emptyAuthzid(self):
        """
        Properly parse an empty authzid.
        """
        c = plain.SASLPlainChallenger()
        cred = c.processResponse("\0chris\0secret")
        self.assertEquals(cred.username, "chris")
        self.assertTrue(cred.checkPassword("secret"))

