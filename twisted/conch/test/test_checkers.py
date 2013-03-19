# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.checkers}.
"""

try:
    import crypt
except ImportError:
    cryptSkip = 'cannot run without crypt module'
else:
    cryptSkip = None

import os, base64

from twisted.python import util
from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import UsernamePassword, IUsernamePassword, \
    SSHPrivateKey, ISSHPrivateKey
from twisted.cred.error import UnhandledCredentials, UnauthorizedLogin
from twisted.python.fakepwd import UserDatabase, ShadowDatabase
from twisted.test.test_process import MockOS

try:
    import Crypto.Cipher.DES3
    import pyasn1
except ImportError:
    dependencySkip = "can't run without Crypto and PyASN1"
else:
    dependencySkip = None
    from twisted.conch.ssh import keys
    from twisted.conch import checkers
    from twisted.conch.error import NotEnoughAuthentication, ValidPublicKey
    from twisted.conch.test import keydata

if getattr(os, 'geteuid', None) is None:
    euidSkip = "Cannot run without effective UIDs (questionable)"
else:
    euidSkip = None


class HelperTests(TestCase):
    """
    Tests for helper functions L{verifyCryptedPassword}, L{_pwdGetByName} and
    L{_shadowGetByName}.
    """
    skip = cryptSkip or dependencySkip

    def setUp(self):
        self.mockos = MockOS()


    def test_verifyCryptedPassword(self):
        """
        L{verifyCryptedPassword} returns C{True} if the plaintext password
        passed to it matches the encrypted password passed to it.
        """
        password = 'secret string'
        salt = 'salty'
        crypted = crypt.crypt(password, salt)
        self.assertTrue(
            checkers.verifyCryptedPassword(crypted, password),
            '%r supposed to be valid encrypted password for %r' % (
                crypted, password))


    def test_verifyCryptedPasswordMD5(self):
        """
        L{verifyCryptedPassword} returns True if the provided cleartext password
        matches the provided MD5 password hash.
        """
        password = 'password'
        salt = '$1$salt'
        crypted = crypt.crypt(password, salt)
        self.assertTrue(
            checkers.verifyCryptedPassword(crypted, password),
            '%r supposed to be valid encrypted password for %s' % (
                crypted, password))


    def test_refuteCryptedPassword(self):
        """
        L{verifyCryptedPassword} returns C{False} if the plaintext password
        passed to it does not match the encrypted password passed to it.
        """
        password = 'string secret'
        wrong = 'secret string'
        crypted = crypt.crypt(password, password)
        self.assertFalse(
            checkers.verifyCryptedPassword(crypted, wrong),
            '%r not supposed to be valid encrypted password for %s' % (
                crypted, wrong))


    def test_pwdGetByName(self):
        """
        L{_pwdGetByName} returns a tuple of items from the UNIX /etc/passwd
        database if the L{pwd} module is present.
        """
        userdb = UserDatabase()
        userdb.addUser(
            'alice', 'secrit', 1, 2, 'first last', '/foo', '/bin/sh')
        self.patch(checkers, 'pwd', userdb)
        self.assertEquals(
            checkers._pwdGetByName('alice'), userdb.getpwnam('alice'))


    def test_pwdGetByNameWithoutPwd(self):
        """
        If the C{pwd} module isn't present, L{_pwdGetByName} returns C{None}.
        """
        self.patch(checkers, 'pwd', None)
        self.assertIdentical(checkers._pwdGetByName('alice'), None)


    def test_shadowGetByName(self):
        """
        L{_shadowGetByName} returns a tuple of items from the UNIX /etc/shadow
        database if the L{spwd} is present.
        """
        userdb = ShadowDatabase()
        userdb.addUser('bob', 'passphrase', 1, 2, 3, 4, 5, 6, 7)
        self.patch(checkers, 'spwd', userdb)

        self.mockos.euid = 2345
        self.mockos.egid = 1234
        self.patch(checkers, 'os', self.mockos)
        self.patch(util, 'os', self.mockos)

        self.assertEquals(
            checkers._shadowGetByName('bob'), userdb.getspnam('bob'))
        self.assertEquals(self.mockos.seteuidCalls, [0, 2345])
        self.assertEquals(self.mockos.setegidCalls, [0, 1234])


    def test_shadowGetByNameWithoutSpwd(self):
        """
        L{_shadowGetByName} uses the C{shadow} module to return a tuple of items
        from the UNIX /etc/shadow database if the C{spwd} module is not present
        and the C{shadow} module is.
        """
        userdb = ShadowDatabase()
        userdb.addUser('bob', 'passphrase', 1, 2, 3, 4, 5, 6, 7)
        self.patch(checkers, 'spwd', None)
        self.patch(checkers, 'shadow', userdb)
        self.patch(checkers, 'os', self.mockos)
        self.patch(util, 'os', self.mockos)

        self.mockos.euid = 2345
        self.mockos.egid = 1234

        self.assertEquals(
            checkers._shadowGetByName('bob'), userdb.getspnam('bob'))
        self.assertEquals(self.mockos.seteuidCalls, [0, 2345])
        self.assertEquals(self.mockos.setegidCalls, [0, 1234])


    def test_shadowGetByNameWithoutEither(self):
        """
        L{_shadowGetByName} returns C{None} if neither C{spwd} nor C{shadow} is
        present.
        """
        self.patch(checkers, 'spwd', None)
        self.patch(checkers, 'shadow', None)
        self.patch(checkers, 'os', self.mockos)

        self.assertIdentical(checkers._shadowGetByName('bob'), None)
        self.assertEquals(self.mockos.seteuidCalls, [])
        self.assertEquals(self.mockos.setegidCalls, [])



class SSHPublicKeyDatabaseTestCase(TestCase):
    """
    Tests for L{SSHPublicKeyDatabase}.
    """
    skip = euidSkip or dependencySkip

    def setUp(self):
        self.checker = checkers.SSHPublicKeyDatabase()
        self.key1 = base64.encodestring("foobar")
        self.key2 = base64.encodestring("eggspam")
        self.content = "t1 %s foo\nt2 %s egg\n" % (self.key1, self.key2)

        self.mockos = MockOS()
        self.mockos.path = FilePath(self.mktemp())
        self.mockos.path.makedirs()
        self.patch(checkers, 'os', self.mockos)
        self.patch(util, 'os', self.mockos)
        self.sshDir = self.mockos.path.child('.ssh')
        self.sshDir.makedirs()

        userdb = UserDatabase()
        userdb.addUser(
            'user', 'password', 1, 2, 'first last',
            self.mockos.path.path, '/bin/shell')
        self.checker._userdb = userdb


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
        self.assertEqual(self.mockos.seteuidCalls, [])
        self.assertEqual(self.mockos.setegidCalls, [])


    def test_checkKey2(self):
        """
        L{SSHPublicKeyDatabase.checkKey} should retrieve the content of the
        authorized_keys2 file and check the keys against that file.
        """
        self._testCheckKey("authorized_keys2")
        self.assertEqual(self.mockos.seteuidCalls, [])
        self.assertEqual(self.mockos.setegidCalls, [])


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
        savedSeteuid = self.mockos.seteuid
        def seteuid(euid):
            keyFile.chmod(0777)
            return savedSeteuid(euid)
        self.mockos.euid = 2345
        self.mockos.egid = 1234
        self.patch(self.mockos, "seteuid", seteuid)
        self.patch(checkers, 'os', self.mockos)
        self.patch(util, 'os', self.mockos)
        user = UsernamePassword("user", "password")
        user.blob = "foobar"
        self.assertTrue(self.checker.checkKey(user))
        self.assertEqual(self.mockos.seteuidCalls, [0, 1, 0, 2345])
        self.assertEqual(self.mockos.setegidCalls, [2, 1234])


    def test_requestAvatarId(self):
        """
        L{SSHPublicKeyDatabase.requestAvatarId} should return the avatar id
        passed in if its C{_checkKey} method returns True.
        """
        def _checkKey(ignored):
            return True
        self.patch(self.checker, 'checkKey', _checkKey)
        credentials = SSHPrivateKey(
            'test', 'ssh-rsa', keydata.publicRSA_openssh, 'foo',
            keys.Key.fromString(keydata.privateRSA_openssh).sign('foo'))
        d = self.checker.requestAvatarId(credentials)
        def _verify(avatarId):
            self.assertEqual(avatarId, 'test')
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
        credentials = SSHPrivateKey(
            'test', 'ssh-rsa', keydata.publicRSA_openssh, None, None)
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
        credentials = SSHPrivateKey(
            'test', 'ssh-rsa', keydata.publicRSA_openssh, 'foo',
            keys.Key.fromString(keydata.privateDSA_openssh).sign('foo'))
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

    skip = dependencySkip

    def test_registerChecker(self):
        """
        L{SSHProcotolChecker.registerChecker} should add the given checker to
        the list of registered checkers.
        """
        checker = checkers.SSHProtocolChecker()
        self.assertEqual(checker.credentialInterfaces, [])
        checker.registerChecker(checkers.SSHPublicKeyDatabase(), )
        self.assertEqual(checker.credentialInterfaces, [ISSHPrivateKey])
        self.assertIsInstance(checker.checkers[ISSHPrivateKey],
                              checkers.SSHPublicKeyDatabase)


    def test_registerCheckerWithInterface(self):
        """
        If a apecific interface is passed into
        L{SSHProtocolChecker.registerChecker}, that interface should be
        registered instead of what the checker specifies in
        credentialIntefaces.
        """
        checker = checkers.SSHProtocolChecker()
        self.assertEqual(checker.credentialInterfaces, [])
        checker.registerChecker(checkers.SSHPublicKeyDatabase(),
                                IUsernamePassword)
        self.assertEqual(checker.credentialInterfaces, [IUsernamePassword])
        self.assertIsInstance(checker.checkers[IUsernamePassword],
                              checkers.SSHPublicKeyDatabase)


    def test_requestAvatarId(self):
        """
        L{SSHProtocolChecker.requestAvatarId} should defer to one if its
        registered checkers to authenticate a user.
        """
        checker = checkers.SSHProtocolChecker()
        passwordDatabase = InMemoryUsernamePasswordDatabaseDontUse()
        passwordDatabase.addUser('test', 'test')
        checker.registerChecker(passwordDatabase)
        d = checker.requestAvatarId(UsernamePassword('test', 'test'))
        def _callback(avatarId):
            self.assertEqual(avatarId, 'test')
        return d.addCallback(_callback)


    def test_requestAvatarIdWithNotEnoughAuthentication(self):
        """
        If the client indicates that it is never satisfied, by always returning
        False from _areDone, then L{SSHProtocolChecker} should raise
        L{NotEnoughAuthentication}.
        """
        checker = checkers.SSHProtocolChecker()
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
        checker = checkers.SSHProtocolChecker()
        d = checker.requestAvatarId(UsernamePassword('test', 'test'))
        return self.assertFailure(d, UnhandledCredentials)


    def test_areDone(self):
        """
        The default L{SSHProcotolChecker.areDone} should simply return True.
        """
        self.assertEquals(checkers.SSHProtocolChecker().areDone(None), True)



class UNIXPasswordDatabaseTests(TestCase):
    """
    Tests for L{UNIXPasswordDatabase}.
    """
    skip = cryptSkip or dependencySkip

    def assertLoggedIn(self, d, username):
        """
        Assert that the L{Deferred} passed in is called back with the value
        'username'.  This represents a valid login for this TestCase.

        NOTE: To work, this method's return value must be returned from the
        test method, or otherwise hooked up to the test machinery.

        @param d: a L{Deferred} from an L{IChecker.requestAvatarId} method.
        @type d: L{Deferred}
        @rtype: L{Deferred}
        """
        result = []
        d.addBoth(result.append)
        self.assertEquals(len(result), 1, "login incomplete")
        if isinstance(result[0], Failure):
            result[0].raiseException()
        self.assertEquals(result[0], username)


    def test_defaultCheckers(self):
        """
        L{UNIXPasswordDatabase} with no arguments has checks the C{pwd} database
        and then the C{spwd} database.
        """
        checker = checkers.UNIXPasswordDatabase()

        def crypted(username, password):
            salt = crypt.crypt(password, username)
            crypted = crypt.crypt(password, '$1$' + salt)
            return crypted

        pwd = UserDatabase()
        pwd.addUser('alice', crypted('alice', 'password'),
                    1, 2, 'foo', '/foo', '/bin/sh')
        # x and * are convention for "look elsewhere for the password"
        pwd.addUser('bob', 'x', 1, 2, 'bar', '/bar', '/bin/sh')
        spwd = ShadowDatabase()
        spwd.addUser('alice', 'wrong', 1, 2, 3, 4, 5, 6, 7)
        spwd.addUser('bob', crypted('bob', 'password'),
                     8, 9, 10, 11, 12, 13, 14)

        self.patch(checkers, 'pwd', pwd)
        self.patch(checkers, 'spwd', spwd)

        mockos = MockOS()
        self.patch(checkers, 'os', mockos)
        self.patch(util, 'os', mockos)

        mockos.euid = 2345
        mockos.egid = 1234

        cred = UsernamePassword("alice", "password")
        self.assertLoggedIn(checker.requestAvatarId(cred), 'alice')
        self.assertEquals(mockos.seteuidCalls, [])
        self.assertEquals(mockos.setegidCalls, [])
        cred.username = "bob"
        self.assertLoggedIn(checker.requestAvatarId(cred), 'bob')
        self.assertEquals(mockos.seteuidCalls, [0, 2345])
        self.assertEquals(mockos.setegidCalls, [0, 1234])


    def assertUnauthorizedLogin(self, d):
        """
        Asserts that the L{Deferred} passed in is erred back with an
        L{UnauthorizedLogin} L{Failure}.  This reprsents an invalid login for
        this TestCase.

        NOTE: To work, this method's return value must be returned from the
        test method, or otherwise hooked up to the test machinery.

        @param d: a L{Deferred} from an L{IChecker.requestAvatarId} method.
        @type d: L{Deferred}
        @rtype: L{None}
        """
        self.assertRaises(
            checkers.UnauthorizedLogin, self.assertLoggedIn, d, 'bogus value')


    def test_passInCheckers(self):
        """
        L{UNIXPasswordDatabase} takes a list of functions to check for UNIX
        user information.
        """
        password = crypt.crypt('secret', 'secret')
        userdb = UserDatabase()
        userdb.addUser('anybody', password, 1, 2, 'foo', '/bar', '/bin/sh')
        checker = checkers.UNIXPasswordDatabase([userdb.getpwnam])
        self.assertLoggedIn(
            checker.requestAvatarId(UsernamePassword('anybody', 'secret')),
            'anybody')


    def test_verifyPassword(self):
        """
        If the encrypted password provided by the getpwnam function is valid
        (verified by the L{verifyCryptedPassword} function), we callback the
        C{requestAvatarId} L{Deferred} with the username.
        """
        def verifyCryptedPassword(crypted, pw):
            return crypted == pw
        def getpwnam(username):
            return [username, username]
        self.patch(checkers, 'verifyCryptedPassword', verifyCryptedPassword)
        checker = checkers.UNIXPasswordDatabase([getpwnam])
        credential = UsernamePassword('username', 'username')
        self.assertLoggedIn(checker.requestAvatarId(credential), 'username')


    def test_failOnKeyError(self):
        """
        If the getpwnam function raises a KeyError, the login fails with an
        L{UnauthorizedLogin} exception.
        """
        def getpwnam(username):
            raise KeyError(username)
        checker = checkers.UNIXPasswordDatabase([getpwnam])
        credential = UsernamePassword('username', 'username')
        self.assertUnauthorizedLogin(checker.requestAvatarId(credential))


    def test_failOnBadPassword(self):
        """
        If the verifyCryptedPassword function doesn't verify the password, the
        login fails with an L{UnauthorizedLogin} exception.
        """
        def verifyCryptedPassword(crypted, pw):
            return False
        def getpwnam(username):
            return [username, username]
        self.patch(checkers, 'verifyCryptedPassword', verifyCryptedPassword)
        checker = checkers.UNIXPasswordDatabase([getpwnam])
        credential = UsernamePassword('username', 'username')
        self.assertUnauthorizedLogin(checker.requestAvatarId(credential))


    def test_loopThroughFunctions(self):
        """
        UNIXPasswordDatabase.requestAvatarId loops through each getpwnam
        function associated with it and returns a L{Deferred} which fires with
        the result of the first one which returns a value other than None.
        ones do not verify the password.
        """
        def verifyCryptedPassword(crypted, pw):
            return crypted == pw
        def getpwnam1(username):
            return [username, 'not the password']
        def getpwnam2(username):
            return [username, username]
        self.patch(checkers, 'verifyCryptedPassword', verifyCryptedPassword)
        checker = checkers.UNIXPasswordDatabase([getpwnam1, getpwnam2])
        credential = UsernamePassword('username', 'username')
        self.assertLoggedIn(checker.requestAvatarId(credential), 'username')


    def test_failOnSpecial(self):
        """
        If the password returned by any function is C{""}, C{"x"}, or C{"*"} it
        is not compared against the supplied password.  Instead it is skipped.
        """
        pwd = UserDatabase()
        pwd.addUser('alice', '', 1, 2, '', 'foo', 'bar')
        pwd.addUser('bob', 'x', 1, 2, '', 'foo', 'bar')
        pwd.addUser('carol', '*', 1, 2, '', 'foo', 'bar')
        self.patch(checkers, 'pwd', pwd)

        checker = checkers.UNIXPasswordDatabase([checkers._pwdGetByName])
        cred = UsernamePassword('alice', '')
        self.assertUnauthorizedLogin(checker.requestAvatarId(cred))

        cred = UsernamePassword('bob', 'x')
        self.assertUnauthorizedLogin(checker.requestAvatarId(cred))

        cred = UsernamePassword('carol', '*')
        self.assertUnauthorizedLogin(checker.requestAvatarId(cred))
