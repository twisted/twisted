# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.win32}.
"""

from twisted.trial import unittest
from twisted.python.runtime import platform
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
        self.assertEqual(win32.cmdLineQuote('an_argument'), 'an_argument')


    def test_argWithSpaces(self):
        """
        Calling C{cmdLineQuote} with an argument containing spaces should
        return the argument surrounded by quotes.
        """
        self.assertEqual(win32.cmdLineQuote('An Argument'), '"An Argument"')


    def test_emptyStringArg(self):
        """
        Calling C{cmdLineQuote} with an empty string should return a
        quoted empty string.
        """
        self.assertEqual(win32.cmdLineQuote(''), '""')



class ProgramPathsTests(unittest.TestCase):
    """
    Tests for L{getProgramsMenuPath} and L{getProgramFilesPath}.
    """

    def test_getProgramsMenuPath(self):
        """
        L{getProgramsMenuPath} guesses the programs menu path on non-win32
        platforms. On non-win32 it will try to figure out the path by
        examining the registry.
        """
        if not platform.isWindows():
            self.assertEqual(win32.getProgramsMenuPath(),
                "C:\\Windows\\Start Menu\\Programs")
        else:
            self.assertIsInstance(win32.getProgramsMenuPath(), str)


    def test_getProgramFilesPath(self):
        """
        L{getProgramFilesPath} returns the "program files" path on win32.
        """
        self.assertIsInstance(win32.getProgramFilesPath(), str)

    if not platform.isWindows():
        test_getProgramFilesPath.skip = (
            "Cannot figure out the program files path on non-win32 platform")


    def test_deprecationGetProgramFilesPath(self):
        """
        L{getProgramFilesPath} has been deprecated.
        """
        win32.getProgramFilesPath()

        emittedWarnings = self.flushWarnings(
            [self.test_deprecationGetProgramFilesPath])
        self.assertEqual(len(emittedWarnings), 1)
        self.assertIs(emittedWarnings[0]["category"], DeprecationWarning)
        self.assertEqual(
            emittedWarnings[0]["message"],
            "twisted.python.win32.getProgramFilesPath was deprecated in "
            "Twisted 15.3.0")

    if not platform.isWindows():
        test_deprecationGetProgramFilesPath.skip = (
            "Deprecation test for getProgramFilesPath() is Windows only")


    def test_deprecationGetProgramsMenuPath(self):
        """
        L{getProgramsMenuPath} has been deprecated.
        """
        win32.getProgramsMenuPath()

        emittedWarnings = self.flushWarnings(
            [self.test_deprecationGetProgramsMenuPath])
        self.assertEqual(len(emittedWarnings), 1)
        self.assertIs(emittedWarnings[0]["category"], DeprecationWarning)
        self.assertEqual(
            emittedWarnings[0]["message"],
            "twisted.python.win32.getProgramsMenuPath was deprecated in "
            "Twisted 15.3.0")
