# Copyright (c) 2007-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for generic file descriptor based reactor support code.
"""

from twisted.trial.unittest import TestCase

from twisted.internet.abstract import isIPAddress
from twisted.internet.abstract import isIPv6Address


class AddressTests(TestCase):
    """
    Tests for address-related functionality.
    """
    def test_decimalDotted(self):
        """
        L{isIPAddress} should return C{True} for any decimal dotted
        representation of an IPv4 address.
        """
        self.assertTrue(isIPAddress('0.1.2.3'))
        self.assertTrue(isIPAddress('252.253.254.255'))


    def test_shortDecimalDotted(self):
        """
        L{isIPAddress} should return C{False} for a dotted decimal
        representation with fewer or more than four octets.
        """
        self.assertFalse(isIPAddress('0'))
        self.assertFalse(isIPAddress('0.1'))
        self.assertFalse(isIPAddress('0.1.2'))
        self.assertFalse(isIPAddress('0.1.2.3.4'))


    def test_invalidLetters(self):
        """
        L{isIPAddress} should return C{False} for any non-decimal dotted
        representation including letters.
        """
        self.assertFalse(isIPAddress('a.2.3.4'))
        self.assertFalse(isIPAddress('1.b.3.4'))


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
        L{isIPAddress} should return C{False} for a string containing
        positive decimal values greater than 255.
        """
        self.assertFalse(isIPAddress('256.0.0.0'))
        self.assertFalse(isIPAddress('0.256.0.0'))
        self.assertFalse(isIPAddress('0.0.256.0'))
        self.assertFalse(isIPAddress('0.0.0.256'))
        self.assertFalse(isIPAddress('256.256.256.256'))



class IPv6AddressTests(TestCase):
    """
    Tests for IPv6 addresses.
    """

    def test_hexadecimalColoned(self):
        """
        L{isIPv6Address} should return C{True} for any valid colon-separated
        hexadecimal representation of an IPv6 address.
        """
        self.assertTrue(isIPv6Address('::1'))
        self.assertTrue(isIPv6Address('fe80::215:cbfe:feac:8888'))
        self.assertTrue(isIPv6Address('fe80::215:cbfe:feac:8888'))
        self.assertTrue(isIPv6Address('fe80:5:5:5:215:cbfe:feac:8888'))


    def test_illegalHexadecimalColoned(self):
        """
        L{isIPv6Address} should return C{False} for any invalid colon-separated
        hexadecimal representation of an IPv6 address.
        """
        self.assertFalse(isIPv6Address(':1::2'))
        self.assertFalse(isIPv6Address('fe80:5:5:5:215:cbfe:feac:8888:5'))
        self.assertFalse(isIPv6Address('g::h'))
