# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.bytes}.
"""

from __future__ import division, absolute_import, print_function

from twisted.python.bytes import toBytes
from twisted.trial.unittest import TestCase



class ToBytesTests(TestCase):
    """
    L{twisted.python.bytes.toBytes} is used to convert L{unicode} to L{bytes}.
    """

    def test_toBytesUnicode(self):
        """
        If L{unicode} is passed to L{toBytes}, the L{unicode} is converted
        to L{bytes} and returned.
        """
        self.assertEqual(toBytes(u"hello"), b"hello")


    def test_toBytesEncodingParameter(self):
        """
        The I{encoding} parameter is passed to L{str.encode} and selects the
        codec to use when converting L{unicode} to L{bytes}.
        """
        self.assertEqual(toBytes(u'\N{SNOWMAN}', encoding="utf-8"),
                         b'\xe2\x98\x83')


    def test_toBytesErrorsParameter(self):
        """
        The I{errors} parameter is passed to L{str.encode} and specifies the
        response when the input string cannot be converted according to the
        encoding’s rules.
        """
        self.assertEqual(
            toBytes(u'\N{SNOWMAN}', encoding="ascii", errors="ignore"),
            b'')


    def test_toBytesUnicodeEncodeError(self):
        """
        L{UnicodeEncodedError} will be raised if the input string cannot be
        converted using the encoding's rules.
        """
        self.assertRaises(UnicodeEncodeError,
            toBytes, u'\N{SNOWMAN}', encoding="ascii")


    def test_toBytesBytes(self):
        """
        L{toBytes} just returns any L{bytes} passed to it.
        """
        self.assertEqual(toBytes(b'\xe2\x98\x83'), b'\xe2\x98\x83')


    def test_toBytesNone(self):
        """
        L{toBytes} just returns L{None} if L{None} was passed to it.
        """
        self.assertEqual(toBytes(None), None)


    def test_toBytesTypeError(self):
        """
        L{toBytes} will raise L{TypeError} if passed anything which
        is not L{unicode}, L{bytes}, or L{None}.
        """
        self.assertRaises(TypeError, toBytes, ["foo", "bar"])
