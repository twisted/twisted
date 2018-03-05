# -*- coding: utf-8 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.bytes}.
"""

from __future__ import division, absolute_import, print_function

from twisted.python.bytes import ensureBytes
from twisted.trial.unittest import TestCase



class EnsureBytesTests(TestCase):
    """
    L{twisted.python.bytes.ensureBytes} is used to convert L{unicode} to
    L{bytes}.
    """

    def test_ensureBytesUnicode(self):
        """
        If L{unicode} is passed to L{ensureBytes}, the L{unicode} is converted
        to L{bytes} and returned.
        """
        self.assertEqual(b"hello", ensureBytes(u"hello"))


    def test_ensureBytesEncodingParameter(self):
        """
        The I{encoding} parameter is passed to L{str.encode} and selects the
        codec to use when converting L{unicode} to L{bytes}.
        """
        self.assertEqual(
            b'\xe2\x98\x83',
            ensureBytes(u'\N{SNOWMAN}', encoding="utf-8"))


    def test_ensureBytesErrorsParameter(self):
        """
        The I{errors} parameter is passed to L{str.encode} and specifies the
        response when the input string cannot be converted according to the
        encoding’s rules.
        """
        self.assertEqual(
            b'',
            ensureBytes(u'\N{SNOWMAN}', encoding="ascii", errors="ignore"))


    def test_ensureBytesUnicodeEncodeError(self):
        """
        L{UnicodeEncodedError} will be raised if the input string cannot be
        converted using the encoding's rules.
        """
        self.assertRaises(
            UnicodeEncodeError,
            ensureBytes, u'\N{SNOWMAN}', encoding="ascii")


    def test_ensureBytesBytes(self):
        """
        L{ensureBytes} just returns any L{bytes} passed to it.
        """
        self.assertEqual(b'\xe2\x98\x83', ensureBytes(b'\xe2\x98\x83'))
