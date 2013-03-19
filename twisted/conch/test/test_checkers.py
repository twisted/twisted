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

import base64
import errno
import os

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
    Tests for helper functions L{checkers.verifyCryptedPassword},
    L{checkers._pwdGetByName}, and L{checkers._shadowGetByName}
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



class KeyFromXTestsCases(TestCase):
    """
    Tests for L{checkers.keysFromString} and L{checkers.keysFromFilepaths}
    """
    def setUp(self):
        self.keyCalls = []

        class FakeKey(object):
            @classmethod
            def fromString(cls, *args, **kwargs):
                self.keyCalls.append((args, kwargs))
                return "this is a key!"

        self.patch(checkers.keys, 'Key', FakeKey)

        class FakeFilePath(object):
            def getContents(self):
                return 'contents'

            def exists(self):
                return True

        self.patch(checkers, 'FilePath', FakeFilePath)


    def test_keysFromStrings(self):
        """
        L{checkers.keysFromStrings} produces a generator of key objects given
        a list of strings and passes whatever key type was supplied
        """
        result = checkers.keysFromStrings('iterable', keyType='skeleton')
        self.assertEqual(self.keyCalls, [],
                         "It's a generator, there should be no calls yet")
        result = list(result)
        self.assertEqual(
            self.keyCalls,
            [((letter,), {'type': 'skeleton'}) for letter in 'iterable'])
        self.assertEqual(result, ['this is a key!'] * len('iterable'))


    def test_keysFromStringsDefaultKeytype(self):
        """
        L{checkers.keysFromStrings} passes the default keytype if no keytype is
        supplied
        """
        list(checkers.keysFromStrings('iterable'))
        self.assertEqual(
            self.keyCalls,
            [((letter,), {'type': 'public_openssh'}) for letter in 'iterable'])


    def test_keysFromFilepaths(self):
        """
        L{checkers.keysFromFilepaths} produces a generator of key objects given
        a list of FilePaths and passes whatever key type was supplied.  In this
        test case, we have permission to access the files.
        """
        class FakeFilePath(object):
            def getContents(self):
                return 'contents'

        result = checkers.keysFromFilepaths(
            [checkers.FilePath() for i in range(5)], keyType='skeleton')
        self.assertEqual(self.keyCalls, [],
                         "It's a generator, there should be no calls yet")
        result = list(result)
        self.assertEqual(self.keyCalls,
                         [(('contents',), {'type': 'skeleton'})] * 5)
        self.assertEqual(result, ['this is a key!'] * 5)


    def test_keysFromFilepathsDefaultKeytype(self):
        """
        L{checkers.keysFromFilepaths} passes the default keytype if no keytype
        is supplied
        """
        list(checkers.keysFromFilepaths(
            [checkers.FilePath() for i in range(5)]))
        self.assertEqual(self.keyCalls,
                         [(('contents',), {'type': 'public_openssh'})] * 5)


    def test_keysFromFilepathsFiltersNonexistentKeypaths(self):
        """
        L{checkers.keysFromFilepaths} produces a generator of key objects given
        a list of FilePaths, but only those FilePaths that exist.
        """
        class FakeFilePath(object):
            def getContents(self):
                return 'contents'

            def exists(self):
                return False

        self.assertEqual([], list(
            checkers.keysFromFilepaths([FakeFilePath() for i in range(5)])))


    def test_keysFromFilepathsInvalidPermissionsWithOwnerIds(self):
        """
        L{checkers.keysFromFilepaths}, if a FilePath cannot be accessed due to
        permissions, if owner ids are provided, attempts to open them again
        using those owner ids before giving up
        """
        class FakeFilePath(object):
            errored = False

            def getContents(self):
                if not self.errored:
                    self.errored = True
                    raise IOError(errno.EACCES, "this is a test")
                return 'contents'

            def exists(self):
                return True

        runAsUserCalls = []

        def _fakeRunAsUser(uid, gid, function, *args, **kwargs):
            runAsUserCalls.append((uid, gid))
            return function(*args, **kwargs)

        self.patch(checkers, 'runAsEffectiveUser', _fakeRunAsUser)

        list(checkers.keysFromFilepaths([FakeFilePath() for i in range(5)],
                                        ownerIds=(1, 1)))
        self.assertEqual(self.keyCalls,
                         [(('contents',), {'type': 'public_openssh'})] * 5)
        self.assertEqual(runAsUserCalls, [(1, 1)] * 5)


class AuthenticateAndVerifySSHKeyHelpers(TestCase):
    """
    Tests for L{checkers.authenticateAndVerifySSHKey}
    """
    def setUp(self):
        class FakeKey(object):
            """
            This generator never ends - will produce FakeKey objects forever,
            and the count of C{keysGenerated} will keep increasing
            """
            @classmethod
            def fromString(cls, *args, **kwargs):
                return FakeKey(args[0])

            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return self.value == other.value

            def verify(self, signature, sigData):
                return signature == 'signature'

        self.patch(checkers.keys, 'Key', FakeKey)

        self.credentials = SSHPrivateKey(
            'username', 'rsa', 5, 'sigData', 'signature')

        self.keysGenerated = 0

        def generate():
            """
            This generator never ends - will produce FakeKey objects until 20,
            and the count of C{keysGenerated} will keep increasing
            """
            while self.keysGenerated < 20:
                self.keysGenerated += 1
                yield FakeKey(self.keysGenerated)

        self.generator = generate()


    def test_validKeyAndValidSignature(self):
        """
        L{checkers.authenticateAndVerifySSHKey} checks the blob against
        a set of authorized keys (and only enough of them to authenticate the
        key), and when the signature checks out, returns the username provided
        with the credentials.
        """
        self.assertEqual(
            'username', checkers.authenticateAndVerifySSHKey(
                self.generator, self.credentials))
        self.assertEqual(self.keysGenerated, 5)


    def test_validKeyNoSignature(self):
        """
        If L{checkers.authenticateAndVerifySSHKey} matches the blob against
        the authorized keys but there is no signature, it raises
        L{ValidPublicKey}.
        """
        self.credentials.signature = None
        self.assertRaises(ValidPublicKey, checkers.authenticateAndVerifySSHKey,
                          self.generator, self.credentials)
        # should match the blob anyway
        self.assertEqual(self.keysGenerated, 5)


    def test_invalidKeyNoSignature(self):
        """
        If L{checkers.authenticateAndVerifySSHKey} fails to matches the blob
        against the authorized keys and there is no signature, it raises
        L{UnauthorizedLogin}.
        """
        self.credentials.signature = None
        self.credentials.blob = 100
        self.assertRaises(UnauthorizedLogin,
                          checkers.authenticateAndVerifySSHKey,
                          self.generator, self.credentials)
        # should have tried to match all the blobs anyway
        self.assertEqual(self.keysGenerated, 20)


    def test_validKeyInvalidSignature(self):
        """
        If L{checkers.authenticateAndVerifySSHKey} matches the blob against
        the authorized keys and there is a signature but it doesn't match,
        it raises L{UnauthorizedLogin}.
        """
        self.credentials.signature = 'wrong'
        self.assertRaises(UnauthorizedLogin,
                          checkers.authenticateAndVerifySSHKey,
                          self.generator, self.credentials)
        self.assertEqual(self.keysGenerated, 5)


    def test_validKeyErrorVerifyingSignature(self):
        """
        If L{checkers.authenticateAndVerifySSHKey} matches the blob against
        the authorized keys but there is a problem verifying the signature,
        it raises L{UnauthorizedLogin}.
        """
        class FakeKey(object):
            """
            This generator never ends - will produce FakeKey objects forever,
            and the count of C{keysGenerated} will keep increasing
            """
            @classmethod
            def fromString(cls, *args, **kwargs):
                return FakeKey(args[0])

            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return self.value == other.value

            def verify(self, signature, sigData):
                raise Exception('hats are fun')

        self.patch(checkers.keys, 'Key', FakeKey)
        self.assertRaises(UnauthorizedLogin,
                          checkers.authenticateAndVerifySSHKey,
                          self.generator, self.credentials)
        loggedErrors = self.flushLoggedErrors(Exception)
        self.assertEqual(len(loggedErrors), 1)



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

        self.keysFromFilepathsCalls = []
        self.authenticateAndVerifyCalls = []

        self.keysFromFilepathsResult = 'keysFromFilepaths result'
        self.authenticateAndVerifyResult = 'authenticateAndVerify result'

        def _fakeKeysFromFilepaths(*args, **kwargs):
            self.keysFromFilepathsCalls.append((args, kwargs))
            if isinstance(self.keysFromFilepathsResult, Exception):
                raise self.keysFromFilepathsResult
            else:
                return self.keysFromFilepathsResult

        def _fakeAuthenticateAndVerify(*args, **kwargs):
            self.authenticateAndVerifyCalls.append((args, kwargs))
            if isinstance(self.authenticateAndVerifyResult, Exception):
                raise self.authenticateAndVerifyResult
            else:
                return self.authenticateAndVerifyResult

        self.patch(checkers, 'keysFromFilepaths', _fakeKeysFromFilepaths)
        self.patch(checkers, 'authenticateAndVerifySSHKey',
                   _fakeAuthenticateAndVerify)


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
        L{SSHPublicKeyDatabase.requestAvatarId} first gets the authorized
        files, passes it to L{checkers.keysFromFilepaths} along with the uid
        and the gid of the user (which it getes from C{pwd}), and passes the
        the result of L{checkers.keysFromFilepaths} and the credentials to
        L{checkers.authenticateAndVerifySSHKey}.  If no errors occur, it
        returns the result of L{checkers.authenticateAndVerifySSHKey}.
        """
        self.checker.getAuthorizedKeysFiles = lambda creds: [1, 2, 3]
        credentials = SSHPrivateKey('user', 'rsa', 'blob', 'sigData', 'sig')
        d = self.checker.requestAvatarId(credentials)
        self.assertEqual(self.successResultOf(d),
                         'authenticateAndVerify result')
        self.assertEqual(self.keysFromFilepathsCalls,
                         [(([1, 2, 3],), {'ownerIds': (1, 2)})])
        self.assertEqual(self.authenticateAndVerifyCalls,
                         [(('keysFromFilepaths result', credentials), {})])


    def test_requestAvatarIdNormalizeException(self):
        """
        Other exceptions raised in the course of
        L{SSHPublicKeyDatabase.requestAvatarId} (for instance a KeyError from
        attempting to look up a non-existant user in pwd) are normalized into
        an C{UnauthorizedLogin} failure.
        """
        self.checker.getAuthorizedKeysFiles = lambda creds: [1, 2, 3]
        credentials = SSHPrivateKey('bleh', 'rsa', 'blob', 'sigData', 'sig')
        f = self.failureResultOf(self.checker.requestAvatarId(credentials))
        self.assertTrue(f.check(UnauthorizedLogin))
        loggedErrors = self.flushLoggedErrors(KeyError)
        self.assertEqual(len(loggedErrors), 1)



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
