# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.checkers}.
"""

try:
    import pwd
except ImportError:
    pwd = None

import os, base64

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.cred.credentials import UsernamePassword
from twisted.test.test_process import MockOS

try:
    import Crypto.Cipher.DES3
except ImportError:
    SSHPublicKeyDatabase = None
else:
    from twisted.conch.checkers import SSHPublicKeyDatabase



class SSHPublicKeyDatabaseTests(TestCase):
    """
    Tests for L{SSHPublicKeyDatabase}.
    """

    if pwd is None:
        skip = "Cannot run without pwd module"
    elif SSHPublicKeyDatabase is None:
        skip = "Cannot run without PyCrypto"

    def setUp(self):
        self.checker = SSHPublicKeyDatabase()
        self.sshDir = FilePath(self.mktemp())
        self.sshDir.makedirs()

        self.key1 = base64.encodestring("foobar")
        self.key2 = base64.encodestring("eggspam")
        self.content = "t1 %s foo\nt2 %s egg\n" % (self.key1, self.key2)

        self.mockos = MockOS()
        self.mockos.path = self.sshDir.path
        self.patch(os.path, "expanduser", self.mockos.expanduser)
        self.patch(pwd, "getpwnam", self.mockos.getpwnam)
        self.patch(os, "seteuid", self.mockos.seteuid)
        self.patch(os, "setegid", self.mockos.setegid)


    def _testCheckKey(self, filename):
        self.sshDir.child(filename).setContent(self.content)
        user = UsernamePassword("user", "password")
        user.blob = "foobar"
        self.assertTrue(self.checker.checkKey(user))
        user.blob = "eggspam"
        self.assertTrue(self.checker.checkKey(user))
        user.blob = "notallowed"
        self.assertFalse(self.checker.checkKey(user))


    def test_checkKey(self):
        """
        L{SSHPublicKeyDatabase.checkKey} should retrieve the content of the
        authorized_keys file and check the keys against that file.
        """
        self._testCheckKey("authorized_keys")
        self.assertEquals(self.mockos.seteuidCalls, [])
        self.assertEquals(self.mockos.setegidCalls, [])


    def test_checkKey2(self):
        """
        L{SSHPublicKeyDatabase.checkKey} should retrieve the content of the
        authorized_keys2 file and check the keys against that file.
        """
        self._testCheckKey("authorized_keys2")
        self.assertEquals(self.mockos.seteuidCalls, [])
        self.assertEquals(self.mockos.setegidCalls, [])


    def test_checkKeyAsRoot(self):
        """
        If the key file is readable, L{SSHPublicKeyDatabase.checkKey} should
        switch its uid/gid to the ones of the authenticated user.
        """
        keyFile = self.sshDir.child("authorized_keys")
        keyFile.setContent(self.content)
        # Fake permission error by changing the mode
        keyFile.chmod(0000)
        self.addCleanup(keyFile.chmod, 0777)
        # And restore the right mode when seteuid is called
        savedSeteuid = os.seteuid
        def seteuid(euid):
            keyFile.chmod(0777)
            return savedSeteuid(euid)
        self.patch(os, "seteuid", seteuid)
        user = UsernamePassword("user", "password")
        user.blob = "foobar"
        self.assertTrue(self.checker.checkKey(user))
        self.assertEquals(self.mockos.seteuidCalls, [0, 1, 0, os.getuid()])
        self.assertEquals(self.mockos.setegidCalls, [2, os.getgid()])
