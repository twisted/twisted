# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.main}.
"""

from twisted.trial import unittest
from twisted.internet.error import ReactorAlreadyInstalledError
from twisted.internet.main import installReactor


class InstallReactorTests(unittest.TestCase):
    """
    Tests for L{installReactor}
    """

    def test_alreadyInstalled(self):
        """
        If a reactor is already installed, L{installReactor} raises
        L{ReactorAlreadyInstalledError}.
        """
        # Because this test runs in trial, assume a reactor is already
        # installed.
        self.assertRaises(ReactorAlreadyInstalledError, installReactor,
                          object())


    def test_errorIsAnAssertionError(self):
        """
        For backwards compatibility, L{ReactorAlreadyInstalledError} is an
        L{AssertionError}.
        """
        self.assertTrue(issubclass(ReactorAlreadyInstalledError,
                        AssertionError))



