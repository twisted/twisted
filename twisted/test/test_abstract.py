# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for generic file descriptor based reactor support code.
"""

from twisted.trial.unittest import TestCase

from twisted.internet.abstract import isIPAddress


class AddressTests(TestCase):
    """
    Tests for address-related functionality.
    """
    def test_decimalDotted(self):
        """
        L{isIPAddress} should return C{True} for any decimal dotted
        representation of an IPv4 address.
        """
        # Up to 3 dots separating integers between 0 and 255 inclusive is
        # legal.
        self.assertTrue(isIPAddress('0'))
        self.assertTrue(isIPAddress('0.1'))
        self.assertTrue(isIPAddress('0.1.2'))
        self.assertTrue(isIPAddress('0.1.2.3'))
        self.assertTrue(isIPAddress('252.253.254.255'))

    def test_invalidLetters(self):
        """
        L{isIPAddress} should return C{False} for any non-hex dotted
        representation including letters.
        """
        self.assertFalse(isIPAddress('a'))
        self.assertFalse(isIPAddress('a.b'))
        self.assertFalse(isIPAddress('1.b'))
        self.assertFalse(isIPAddress('1.b.2.3'))
        self.assertFalse(isIPAddress('1.b.2.3'))
        self.assertFalse(isIPAddress('1b2c3d4'))


    def test_invalidPunctuation(self):
        """
        L{isIPAddress} should return C{False} for a string containing
        strange punctuation.
        """
        self.assertFalse(isIPAddress(','))
        self.assertFalse(isIPAddress('1,2'))
        self.assertFalse(isIPAddress('1,2,3'))
        self.assertFalse(isIPAddress('1.,.3,4'))


    def test_emptyString(self):
        """
        L{isIPAddress} should return C{False} for the empty string.
        """
        self.assertFalse(isIPAddress(''))


    def test_invalidNegative(self):
        """
        L{isIPAddress} should return C{False} for negative decimal values.
        """
        self.assertFalse(isIPAddress('-1'))
        self.assertFalse(isIPAddress('1.-2'))
        self.assertFalse(isIPAddress('1.2.-3'))
        self.assertFalse(isIPAddress('1.2.-3.4'))


    def test_invalidPositive(self):
        """
        L{isIPAddress} should return C{False} for positive decimal values
        greater than 255 in a dotted quad (when fewer than three dots are
        present, larger values may or may not be allowed).
        """
        self.assertFalse(isIPAddress('256.255.255.255'))
        self.assertFalse(isIPAddress('255.256.255.255'))
        self.assertFalse(isIPAddress('255.255.256.255'))
        self.assertFalse(isIPAddress('255.255.255.256'))
        self.assertFalse(isIPAddress('256.256.256.256'))
