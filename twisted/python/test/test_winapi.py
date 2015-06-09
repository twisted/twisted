# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for C{twisted.python._winapi}
"""

import os
import unittest

from twisted.python import _winapi


class RaiseErrorIfZeroTests(unittest.TestCase):
    """
    Tests for C{twisted.python._winapi.raiseErrorIfZero}.
    """
    def test_raisesTypeError(self):
        """
        TypeError should be raised if the first argument
        to raiseErrorIfZero is not an integer.
        """
        with self.assertRaises(TypeError):
            _winapi.raiseErrorIfZero(1.0, "")


    def test_raisesWindowsAPIError(self):
        """
        Test that _winapi.raiseErrorIfZero(0, "") raises WindowsAPIError
        """
        with self.assertRaises(_winapi.WindowsAPIError):
            _winapi.raiseErrorIfZero(0, "")


    def test_noErrorForPositiveInt(self):
        """
        Test that _winapi.raiseErrorIfZero(1, "") does nothing.  This is
        testing the expected behavior of the function call.
        """
        _winapi.raiseErrorIfZero(1, "")


    def test_noErrorForNegativeInt(self):
        """
        Test that _winapi.raiseErrorIfZero(-1, "") does nothing.

        This test exists to guard against a change that modifies the logic
        of _raiseErrorIfZero from ``if ok == 0:`` to ``if ok >= 0`` or similar
        statement. The type of errors _raiseErrorIfZero handles are
        documented by Microsoft such that any non-zero value is considered
        success.  If this test breaks either _raiseErrorIfZero was updated on
        purpose to allow for a new value or the value being passed into
        _raiseErrorIfZero is incorrect and someone thought they found a bug.
        """
        _winapi.raiseErrorIfZero(-1, "")


    def test_allowsLongForOk(self):
        """
        In Python 2 int and long are two different things, in Python
        3 there's only int.  This test ensures we accept a long when it's
        available because the Windows API can sometimes return a long even
        though a number can fit within an int.
        """
        _winapi.raiseErrorIfZero(_winapi.LONG(1), "")



class OpenProcessTests(unittest.TestCase):
    """
    Tests for C{twisted.python._winapi.OpenProcess}.
    """
    def test_openWithoutAccessRights(self):
        """
        Tests to ensure that the default implementation of OpenProcess()
        remains unchanged.  This is requesting to open the current process
        without any access rights
        """
        with self.assertRaises(_winapi.WindowsAPIError) as error:
            _winapi.OpenProcess(os.getpid())

        self.assertEqual(
            error.exception.code, _winapi.kernel32.ERROR_ACCESS_DENIED)


    def test_canAccessCurrentProcess(self):
        """
        Minimally, we should be able be access the current process
        with some basic query rights.  If we can't, then it's probably
        a bug in our code.
        """
        _winapi.OpenProcess(
            os.getpid(),
            dwDesiredAccess=_winapi.kernel32.PROCESS_QUERY_INFORMATION
        )
