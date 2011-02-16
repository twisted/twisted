# Copyright (c) Twisted Matrix Laboratories.
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
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import UsernamePassword, IUsernamePassword, \
    SSHPrivateKey, ISSHPrivateKey
from twisted.cred.error import UnhandledCredentials, UnauthorizedLogin
from twisted.python.fakepwd import UserDatabase
from twisted.test.test_process import MockOS

try:
    import Crypto.Cipher.DES3
    import pyasn1
except ImportError:
    SSHPublicKeyDatabase = None
else:
    from twisted.conch.ssh import keys
    from twisted.conch.checkers import SSHPublicKeyDatabase, SSHProtocolChecker
    from twisted.conch.error import NotEnoughAuthentication, ValidPublicKey
    from twisted.conch.test import keydata


class SSHPublicKeyDatabaseTestCase(TestCase):
    """
    Tests for L{SSHPublicKeyDatabase}.
    """

    if pwd is None:
        skip = "Cannot run without pwd module"
    elif SSHPublicKeyDatabase is None:
        skip = "Cannot run without PyCrypto or PyASN1"

    def setUp(self):
        self.checker = SSHPublicKeyDatabase()
        self.key1 = base64.encodestring("foobar")
        self.key2 = base64.encodestring("eggspam")
        self.content = "t1 %s foo\nt2 %s egg\n" % (self.key1, self.key2)

        self.mockos = MockOS()
        self.mockos.path = FilePath(self.mktemp())
        self.mockos.path.makedirs()
        self.sshDir = self.mockos.path.child('.ssh')
        self.sshDir.makedirs()

        userdb = UserDatabase()
        userdb.addUser('user', 'password', 1, 2, 'first last',
                self.mockos.path.path, '/bin/shell')

        self.patch(pwd, "getpwnam", userdb.getpwnam)
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


    def test_requestAvatarId(self):
        """
        L{SSHPublicKeyDatabase.requestAvatarId} should return the avatar id
        passed in if its C{_checkKey} method returns True.
        """
        def _checkKey(ignored):
            return True
        self.patch(self.checker, 'checkKey', _checkKey)
        credentials = SSHPrivateKey('test', 'ssh-rsa', keydata.publicRSA_openssh,
                                    'foo', keys.Key.fromString(keydata.privateRSA_openssh).sign('foo'))
        d = self.checker.requestAvatarId(credentials)
        def _verify(avatarId):
            self.assertEquals(avatarId, 'test')
        return d.addCallback(_verify)


    def test_requestAvatarIdWithoutSignature(self):
        """
        L{SSHPublicKeyDatabase.requestAvatarId} should raise L{ValidPublicKey}
        if the credentials represent a valid key without a signature.  This
        tells the user that the key is valid for login, but does not actually
        allow that user to do so without a signature.
        """
        def _checkKey(ignored):
            return True
        self.patch(self.checker, 'checkKey', _checkKey)
        credentials = SSHPrivateKey('test', 'ssh-rsa', keydata.publicRSA_openssh, None, None)
        d = self.checker.requestAvatarId(credentials)
        return self.assertFailure(d, ValidPublicKey)


    def test_requestAvatarIdInvalidKey(self):
        """
        If L{SSHPublicKeyDatabase.checkKey} returns False,
        C{_cbRequestAvatarId} should raise L{UnauthorizedLogin}.
        """
        def _checkKey(ignored):
            return False
        self.patch(self.checker, 'checkKey', _checkKey)
        d = self.checker.requestAvatarId(None);
        return self.assertFailure(d, UnauthorizedLogin)


    def test_requestAvatarIdInvalidSignature(self):
        """
        Valid keys with invalid signatures should cause
        L{SSHPublicKeyDatabase.requestAvatarId} to return a {UnauthorizedLogin}
        failure
        """
        def _checkKey(ignored):
            return True
        self.patch(self.checker, 'checkKey', _checkKey)
        credentials = SSHPrivateKey('test', 'ssh-rsa', keydata.publicRSA_openssh,
                                    'foo', keys.Key.fromString(keydata.privateDSA_openssh).sign('foo'))
        d = self.checker.requestAvatarId(credentials)
        return self.assertFailure(d, UnauthorizedLogin)


    def test_requestAvatarIdNormalizeException(self):
        """
        Exceptions raised while verifying the key should be normalized into an
        C{UnauthorizedLogin} failure.
        """
        def _checkKey(ignored):
            return True
        self.patch(self.checker, 'checkKey', _checkKey)
        credentials = SSHPrivateKey('test', None, 'blob', 'sigData', 'sig')
        d = self.checker.requestAvatarId(credentials)
        def _verifyLoggedException(failure):
            errors = self.flushLoggedErrors(keys.BadKeyError)
            self.assertEqual(len(errors), 1)
            return failure
        d.addErrback(_verifyLoggedException)
        return self.assertFailure(d, UnauthorizedLogin)


class SSHProtocolCheckerTestCase(TestCase):
    """
    Tests for L{SSHProtocolChecker}.
    """

    if SSHPublicKeyDatabase is None:
        skip = "Cannot run without PyCrypto"

    def test_registerChecker(self):
        """
        L{SSHProcotolChecker.registerChecker} should add the given checker to
        the list of registered checkers.
        """
        checker = SSHProtocolChecker()
        self.assertEquals(checker.credentialInterfaces, [])
        checker.registerChecker(SSHPublicKeyDatabase(), )
        self.assertEquals(checker.credentialInterfaces, [ISSHPrivateKey])
        self.assertIsInstance(checker.checkers[ISSHPrivateKey],
                              SSHPublicKeyDatabase)


    def test_registerCheckerWithInterface(self):
        """
        If a apecific interface is passed into
        L{SSHProtocolChecker.registerChecker}, that interface should be
        registered instead of what the checker specifies in
        credentialIntefaces.
        """
        checker = SSHProtocolChecker()
        self.assertEquals(checker.credentialInterfaces, [])
        checker.registerChecker(SSHPublicKeyDatabase(), IUsernamePassword)
        self.assertEquals(checker.credentialInterfaces, [IUsernamePassword])
        self.assertIsInstance(checker.checkers[IUsernamePassword],
                              SSHPublicKeyDatabase)


    def test_requestAvatarId(self):
        """
        L{SSHProtocolChecker.requestAvatarId} should defer to one if its
        registered checkers to authenticate a user.
        """
        checker = SSHProtocolChecker()
        passwordDatabase = InMemoryUsernamePasswordDatabaseDontUse()
        passwordDatabase.addUser('test', 'test')
        checker.registerChecker(passwordDatabase)
        d = checker.requestAvatarId(UsernamePassword('test', 'test'))
        def _callback(avatarId):
            self.assertEquals(avatarId, 'test')
        return d.addCallback(_callback)


    def test_requestAvatarIdWithNotEnoughAuthentication(self):
        """
        If the client indicates that it is never satisfied, by always returning
        False from _areDone, then L{SSHProtocolChecker} should raise
        L{NotEnoughAuthentication}.
        """
        checker = SSHProtocolChecker()
        def _areDone(avatarId):
            return False
        self.patch(checker, 'areDone', _areDone)

        passwordDatabase = InMemoryUsernamePasswordDatabaseDontUse()
        passwordDatabase.addUser('test', 'test')
        checker.registerChecker(passwordDatabase)
        d = checker.requestAvatarId(UsernamePassword('test', 'test'))
        return self.assertFailure(d, NotEnoughAuthentication)


    def test_requestAvatarIdInvalidCredential(self):
        """
        If the passed credentials aren't handled by any registered checker,
        L{SSHProtocolChecker} should raise L{UnhandledCredentials}.
        """
        checker = SSHProtocolChecker()
        d = checker.requestAvatarId(UsernamePassword('test', 'test'))
        return self.assertFailure(d, UnhandledCredentials)


    def test_areDone(self):
        """
        The default L{SSHProcotolChecker.areDone} should simply return True.
        """
        self.assertEquals(SSHProtocolChecker().areDone(None), True)
