# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.win32}.
"""

import inspect
import warnings

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


    def test_deprecationWarninggetProgramFilesPath(self):
        """
        Tests to ensure that L{getProgramFilesPath} has been deprecated. A
        call to the deprecated function should cause a deprecation warning
        to be emitted.
        """
        with warnings.catch_warnings(record=True) as emitted_warnings:
            warnings.simplefilter("always")
            win32.getProgramFilesPath()

        if not emitted_warnings:
            self.fail("No warnings emitted")

        self.assertEqual(
            emitted_warnings[0].message.args[0],
            "twisted.python.win32.getProgramFilesPath was deprecated in "
            "Twisted 15.3.0")

    if not platform.isWindows():
        test_deprecationWarninggetProgramFilesPath.skip = (
            "Deprecation test is Windows only")


    def test_deprecatedDocStringgetProgramsMenuPath(self):
        """
        Tests to ensure that L{getProgramFilesPath} has been deprecated.  The
        last line should always be the deprecation message.
        """
        documentation = inspect.getdoc(win32.getProgramsMenuPath)
        self.assertEqual(
            documentation.splitlines()[-1], "Deprecated in Twisted 15.3.0.")


    def test_deprecatedDocStringgetProgramFilesPath(self):
        """
        Tests to ensure that L{getProgramFilesPath} has been deprecated.  The
        last line should always be the deprecation message.
        """
        documentation = inspect.getdoc(win32.getProgramFilesPath)
        self.assertEqual(
            documentation.splitlines()[-1], "Deprecated in Twisted 15.3.0.")


    def test_deprecationWarninggetProgramsMenuPath(self):
        """
        Tests to ensure that L{getProgramsMenuPath} has been deprecated. A
        call to the deprecated function should cause a deprecation warning
        to be emitted.
        """
        with warnings.catch_warnings(record=True) as emitted_warnings:
            warnings.simplefilter("always")
            win32.getProgramsMenuPath()

        if not emitted_warnings:
            self.fail("No warnings emitted")

        self.assertEqual(
            emitted_warnings[0].message.args[0],
            "twisted.python.win32.getProgramsMenuPath was deprecated in "
            "Twisted 15.3.0")
