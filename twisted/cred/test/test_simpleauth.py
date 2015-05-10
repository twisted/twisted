# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for basic constructs of L{twisted.cred.credentials}.
"""

from __future__ import division, absolute_import

from twisted.trial.unittest import TestCase
from twisted.cred.credentials import UsernamePassword


class UsernamePasswordTests(TestCase):
    """
    Tests for L{UsernamePassword}.
    """
    def test_initialisation(self):
        """
        The initialisation of L{UsernamePassword} will set C{username} and
        C{password} on it.
        """
        creds = UsernamePassword(b"foo", b"bar")
        self.assertEqual(creds.username, b"foo")
        self.assertEqual(creds.password, b"bar")


    def test_correctPassword(self):
        """
        Calling C{checkPassword} on a L{UsernamePassword} will return L{True}
        when the password given is the password on the object.
        """
        creds = UsernamePassword(b"user", b"pass")
        self.assertTrue(creds.checkPassword(b"pass"))


    def test_correctPassword(self):
        """
        Calling C{checkPassword} on a L{UsernamePassword} will return L{False}
        when the password given is NOT the password on the object.
        """
        creds = UsernamePassword(b"user", b"pass")
        self.assertTrue(creds.checkPassword(b"someotherpass"))
