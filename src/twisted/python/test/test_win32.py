# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.win32}.
"""

from twisted.trial import unittest
from twisted.python import win32


class CommandLineQuotingTests(unittest.TestCase):
    """
    Tests for L{cmdLineQuote}.
    """

    def test_argWithoutSpaces(self):
        """
        Calling C{cmdLineQuote} with an argument with no spaces should
        return the argument unchanged.
        """
        self.assertEqual(win32.cmdLineQuote("an_argument"), "an_argument")

    def test_argWithSpaces(self):
        """
        Calling C{cmdLineQuote} with an argument containing spaces should
        return the argument surrounded by quotes.
        """
        self.assertEqual(win32.cmdLineQuote("An Argument"), '"An Argument"')

    def test_emptyStringArg(self):
        """
        Calling C{cmdLineQuote} with an empty string should return a
        quoted empty string.
        """
        self.assertEqual(win32.cmdLineQuote(""), '""')


class DeprecationTests(unittest.TestCase):
    """
    Tests for deprecated (Fake)WindowsError.
    """

    def test_deprecation_FakeWindowsError(self):
        """Importing C{FakeWindowsError} should trigger a L{DeprecationWarning}."""

        def import_FakeWindowsError():
            from twisted.python.win32 import FakeWindowsError

            FakeWindowsError  # pretend to use, for flake8

        self.assertWarns(
            DeprecationWarning,
            "twisted.python.win32.FakeWindowsError was deprecated in Twisted NEXT: "
            "Catch OSError and check presence of 'winerror' attribute.",
            __file__,
            import_FakeWindowsError,
        )

    def test_deprecation_WindowsError(self):
        """Importing C{WindowsError} should trigger a L{DeprecationWarning}."""

        def import_WindowsError():
            from twisted.python.win32 import WindowsError

            WindowsError  # pretend to use, for flake8

        self.assertWarns(
            DeprecationWarning,
            "twisted.python.win32.WindowsError was deprecated in Twisted NEXT: "
            "Catch OSError and check presence of 'winerror' attribute.",
            __file__,
            import_WindowsError,
        )
