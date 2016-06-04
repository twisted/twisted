# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{ims.tx.usage._exit}.
"""

import sys

from .._exit import exit, ExitStatus

import twisted.trial.unittest



class ExitTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{exit}.
    """

    def setUp(self):
        self.patch(sys, "exit", self.exit)
        self.exitStatus = None


    def exit(self, status):
        assert self.exitStatus is None
        self.exitStatus = status


    def test_exitStatusInt(self):
        """
        L{exit} given an L{int} status code will pass it to L{sys.exit}.
        """
        status = 1234
        exit(status)
        self.assertEqual(self.exitStatus, status)


    def test_exitStatusStringNotInt(self):
        """
        L{exit} given a L{str} status code that isn't a string integer raises
        L{ValueError}.
        """
        self.assertRaises(ValueError, exit, "foo")


    def test_exitStatusStringInt(self):
        """
        L{exit} given a L{str} status code that is a string integer passes the
        corresponding L{int} to L{sys.exit}.
        """
        exit("1234")
        self.assertEqual(self.exitStatus, 1234)


    def test_exitConstant(self):
        """
        L{exit} given a L{ValueConstant} status code passes the corresponding
        value to L{sys.exit}.
        """
        status = ExitStatus.EX_CONFIG
        exit(status)
        self.assertEqual(self.exitStatus, status.value)
