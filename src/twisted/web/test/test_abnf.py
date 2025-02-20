# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web._abnf}.
"""

from twisted.trial import unittest
from twisted.web._abnf import _decint, _hexint, _ishexdigits, _istoken


class IsTokenTests(unittest.SynchronousTestCase):
    """
    Test the L{twisted.web._abnf._istoken} function.
    """

    def test_ok(self) -> None:
        for b in (
            b"GET",
            b"Cache-Control",
            b"&",
        ):
            self.assertTrue(_istoken(b))

    def test_bad(self) -> None:
        for b in (
            b"",
            b" ",
            b"a b",
        ):
            self.assertFalse(_istoken(b))


class DecintTests(unittest.SynchronousTestCase):
    """
    Test the L{twisted.web._abnf._decint} function.
    """

    def test_valid(self) -> None:
        """
        Given a decimal digits, L{_decint} return an L{int}.
        """
        self.assertEqual(1, _decint(b"1"))
        self.assertEqual(10, _decint(b"10"))
        self.assertEqual(9000, _decint(b"9000"))
        self.assertEqual(9000, _decint(b"0009000"))

    def test_validWhitespace(self) -> None:
        """
        L{_decint} decodes integers embedded in linear whitespace.
        """
        self.assertEqual(123, _decint(b" 123"))
        self.assertEqual(123, _decint(b"123\t\t"))
        self.assertEqual(123, _decint(b" \t 123   \t  "))

    def test_invalidPlus(self) -> None:
        """
        L{_decint} rejects a number with a leading C{+} character.
        """
        self.assertRaises(ValueError, _decint, b"+1")

    def test_invalidMinus(self) -> None:
        """
        L{_decint} rejects a number with a leading C{-} character.
        """
        self.assertRaises(ValueError, _decint, b"-1")

    def test_invalidWhitespace(self) -> None:
        """
        L{_decint} rejects a number embedded in non-linear whitespace.
        """
        self.assertRaises(ValueError, _decint, b"\v1")
        self.assertRaises(ValueError, _decint, b"\x1c1")
        self.assertRaises(ValueError, _decint, b"1\x1e")


class HexHelperTests(unittest.SynchronousTestCase):
    """
    Test the L{twisted.web._abnf._hexint} and L{_ishexdigits} helper functions.
    """

    badStrings = (b"", b"0x1234", b"feds", b"-123" b"+123")

    def test_isHex(self) -> None:
        """
        L{_ishexdigits()} returns L{True} for nonempy bytestrings containing
        hexadecimal digits.
        """
        for s in (b"10", b"abcdef", b"AB1234", b"fed", b"123467890"):
            self.assertIs(True, _ishexdigits(s))

    def test_decodes(self) -> None:
        """
        L{_hexint()} returns the integer equivalent of the input.
        """
        self.assertEqual(10, _hexint(b"a"))
        self.assertEqual(0x10, _hexint(b"10"))
        self.assertEqual(0xABCD123, _hexint(b"abCD123"))

    def test_isNotHex(self) -> None:
        """
        L{_ishexdigits()} returns L{False} for bytestrings that don't contain
        hexadecimal digits, including the empty string.
        """
        for s in self.badStrings:
            self.assertIs(False, _ishexdigits(s))

    def test_decodeNotHex(self) -> None:
        """
        L{_hexint()} raises L{ValueError} for bytestrings that can't
        be decoded.
        """
        for s in self.badStrings:
            self.assertRaises(ValueError, _hexint, s)
