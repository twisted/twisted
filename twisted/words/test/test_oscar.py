# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.protocols.oscar}.
"""

from twisted.trial.unittest import TestCase

from twisted.words.protocols import oscar


class PasswordTests(TestCase):
    """
    Tests for L{oscar.encryptPasswordMD5}.
    """
    def test_encryptPasswordMD5(self):
        """
        L{encryptPasswordMD5} hashes the given password and key and returns a
        string suitable to use to authenticate against an OSCAR server.
        """
        self.assertEqual(
            oscar.encryptPasswordMD5('foo', 'bar').encode('hex'),
            'd73475c370a7b18c6c20386bcf1339f2')



class OSCARUserTests(TestCase):
    """
    Tests for L{oscar.OSCARUser}.
    """
    def setUp(self):
        self.user = oscar.OSCARUser('john', 'debug', {1: '\x00\x01'})


    def test_str(self):
        """
        The string representation of an L{oscar.OSCARUser} includes the name,
        warning level, and flag attributes.
        """
        self.assertEqual(str(self.user),
            "<OSCARUser john, warning level debug, flags ['trial']>")



class SSIGroupTests(TestCase):
    """
    Tests for L{oscar.SSIGroup}.
    """
    def setUp(self):
        self.user = oscar.OSCARUser('jane', 'info', {})


    def test_oscarRep(self):
        """
        L{oscar.SSIGroup.oscarRep} returns a serialized representation of the
        group instance.
        """
        group = oscar.SSIGroup('MyGroup')
        buddyId = 1
        group.addUser(buddyId, self.user)
        self.assertEqual(group.oscarRep(1, buddyId),
            "\x00\x07MyGroup\x00\x01\x00\x01\x00\x01\x00\xc8\x00\x02\x00\x01")



class SSIBuddyTests(TestCase):
    """
    Tests for L{oscar.SSIBuddy}.
    """
    def test_oscarRep(self):
        """
        L{oscar.SSIBuddy.oscarRep} returns a serialized representation of the
        buddy instance.
        """
        buddy = oscar.SSIBuddy('MyBuddy', {1: 'foo'})
        self.assertEqual(buddy.oscarRep(1, 2),
            "\x00\x07MyBuddy\x00\x01\x00\x02\x00\x00"
            "\x00\x00\x00\x01\x00\x03foo")