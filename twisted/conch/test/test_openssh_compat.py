# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.openssh_compat}.
"""

import os

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.python.reflect import requireModule

if requireModule('Crypto.Cipher.DES3') and requireModule('pyasn1'):
    from twisted.conch.openssh_compat.factory import OpenSSHFactory
else:
    OpenSSHFactory = None

from twisted.conch.test import keydata
from twisted.test.test_process import MockOS


class OpenSSHFactoryTests(TestCase):
    """
    Tests for L{OpenSSHFactory}.
    """
    if getattr(os, "geteuid", None) is None:
        skip = "geteuid/seteuid not available"
    elif OpenSSHFactory is None:
        skip = "Cannot run without PyCrypto or PyASN1"


    def setUp(self):
        self.factory = OpenSSHFactory()
        self.keysDir = FilePath(self.mktemp())
        self.keysDir.makedirs()
        self.factory.dataRoot = self.keysDir.path

        self.keysDir.child("ssh_host_foo").setContent("foo")
        self.keysDir.child("bar_key").setContent("foo")
        self.keysDir.child("ssh_host_one_key").setContent(
            keydata.privateRSA_openssh)
        self.keysDir.child("ssh_host_two_key").setContent(
            keydata.privateDSA_openssh)
        self.keysDir.child("ssh_host_three_key").setContent(
            "not a key content")

        self.keysDir.child("ssh_host_one_key.pub").setContent(
            keydata.publicRSA_openssh)

        self.mockos = MockOS()
        self.patch(os, "seteuid", self.mockos.seteuid)
        self.patch(os, "setegid", self.mockos.setegid)


    def test_getPublicKeys(self):
        """
        L{OpenSSHFactory.getPublicKeys} should return the available public keys
        in the data directory
        """
        keys = self.factory.getPublicKeys()
        self.assertEqual(len(keys), 1)
        keyTypes = keys.keys()
        self.assertEqual(keyTypes, ['ssh-rsa'])


    def test_getPrivateKeys(self):
        """
        Will return the available private keys in the data directory, ignoring
        key files which failed to be loaded.
        """
        keys = self.factory.getPrivateKeys()
        self.assertEqual(len(keys), 2)
        keyTypes = keys.keys()
        self.assertEqual(set(keyTypes), set(['ssh-rsa', 'ssh-dss']))
        self.assertEqual(self.mockos.seteuidCalls, [])
        self.assertEqual(self.mockos.setegidCalls, [])


    def test_getPrivateKeysAsRoot(self):
        """
        L{OpenSSHFactory.getPrivateKeys} should switch to root if the keys
        aren't readable by the current user.
        """
        keyFile = self.keysDir.child("ssh_host_two_key")
        # Fake permission error by changing the mode
        keyFile.chmod(0000)
        self.addCleanup(keyFile.chmod, 0777)
        # And restore the right mode when seteuid is called
        savedSeteuid = os.seteuid
        def seteuid(euid):
            keyFile.chmod(0777)
            return savedSeteuid(euid)
        self.patch(os, "seteuid", seteuid)
        keys = self.factory.getPrivateKeys()
        self.assertEqual(len(keys), 2)
        keyTypes = keys.keys()
        self.assertEqual(set(keyTypes), set(['ssh-rsa', 'ssh-dss']))
        self.assertEqual(self.mockos.seteuidCalls, [0, os.geteuid()])
        self.assertEqual(self.mockos.setegidCalls, [0, os.getegid()])
