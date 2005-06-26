# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Now with 30% more starch.
"""

from __future__ import generators

import hmac
from zope import interface

from twisted.trial import unittest
from twisted.cred import portal, checkers, credentials, error
from twisted.python import components
from twisted.python import util
from twisted.internet import defer
from twisted.internet.defer import deferredGenerator as dG, waitForDeferred as wFD

try:
    from crypt import crypt
except ImportError:
    crypt = None

try:
    from twisted.cred.pamauth import callIntoPAM
except ImportError:
    pamauth = None
else:
    from twisted.cred import pamauth

class ITestable(components.Interface):
    pass

class TestAvatar:
    def __init__(self, name):
        self.name = name
        self.loggedIn = False
        self.loggedOut = False

    def login(self):
        assert not self.loggedIn
        self.loggedIn = True

    def logout(self):
        self.loggedOut = True

class Testable(components.Adapter):
    interface.implements(ITestable)

# components.Interface(TestAvatar).adaptWith(Testable, ITestable)

components.registerAdapter(Testable, TestAvatar, ITestable)

class TestRealm:
    interface.implements(portal.IRealm)
    def __init__(self):
        self.avatars = {}

    def requestAvatar(self, avatarId, mind, *interfaces):
        if self.avatars.has_key(avatarId):
            avatar = self.avatars[avatarId]
        else:
            avatar = TestAvatar(avatarId)
            self.avatars[avatarId] = avatar
        avatar.login()
        return (interfaces[0], components.getAdapter(avatar, interfaces[0]),
                avatar.logout)

class NewCredTest(unittest.TestCase):
    def setUp(self):
        r = self.realm = TestRealm()
        p = self.portal = portal.Portal(r)
        up = self.checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        up.addUser("bob", "hello")
        p.registerChecker(up)

    def testListCheckers(self):
        expected = [credentials.IUsernamePassword, credentials.IUsernameHashedPassword]
        got = self.portal.listCredentialsInterfaces()
        expected.sort()
        got.sort()
        self.assertEquals(got, expected)

    def testBasicLogin(self):
        l = []; f = []
        self.portal.login(credentials.UsernamePassword("bob", "hello"),
                          self, ITestable).addCallback(
            l.append).addErrback(f.append)
        if f:
            raise f[0]
        # print l[0].getBriefTraceback()
        iface, impl, logout = l[0]
        # whitebox
        self.assertEquals(iface, ITestable)
        self.failUnless(iface.providedBy(impl),
                        "%s does not implement %s" % (impl, iface))
        # greybox
        self.failUnless(impl.original.loggedIn)
        self.failUnless(not impl.original.loggedOut)
        logout()
        self.failUnless(impl.original.loggedOut)

    def testFailedLogin(self):
        l = []
        self.portal.login(credentials.UsernamePassword("bob", "h3llo"),
                          self, ITestable).addErrback(
            lambda x: x.trap(error.UnauthorizedLogin)).addCallback(l.append)
        self.failUnless(l)
        self.failUnlessEqual(error.UnauthorizedLogin, l[0])

    def testFailedLoginName(self):
        l = []
        self.portal.login(credentials.UsernamePassword("jay", "hello"),
                          self, ITestable).addErrback(
            lambda x: x.trap(error.UnauthorizedLogin)).addCallback(l.append)
        self.failUnless(l)
        self.failUnlessEqual(error.UnauthorizedLogin, l[0])


class CramMD5CredentialsTestCase(unittest.TestCase):
    def testIdempotentChallenge(self):
        c = credentials.CramMD5Credentials()
        chal = c.getChallenge()
        self.assertEquals(chal, c.getChallenge())

    def testCheckPassword(self):
        c = credentials.CramMD5Credentials()
        chal = c.getChallenge()
        c.response = hmac.HMAC('secret', chal).hexdigest()
        self.failUnless(c.checkPassword('secret'))

    def testWrongPassword(self):
        c = credentials.CramMD5Credentials()
        self.failIf(c.checkPassword('secret'))

class OnDiskDatabaseTestCase(unittest.TestCase):
    users = [
        ('user1', 'pass1'),
        ('user2', 'pass2'),
        ('user3', 'pass3'),
    ]


    def testUserLookup(self):
        dbfile = self.mktemp()
        db = checkers.FilePasswordDB(dbfile)
        f = file(dbfile, 'w')
        for (u, p) in self.users:
            f.write('%s:%s\n' % (u, p))
        f.close()

        for (u, p) in self.users:
            self.failUnlessRaises(KeyError, db.getUser, u.upper())
            self.assertEquals(db.getUser(u), (u, p))

    def testCaseInSensitivity(self):
        dbfile = self.mktemp()
        db = checkers.FilePasswordDB(dbfile, caseSensitive=0)
        f = file(dbfile, 'w')
        for (u, p) in self.users:
            f.write('%s:%s\n' % (u, p))
        f.close()

        for (u, p) in self.users:
            self.assertEquals(db.getUser(u.upper()), (u, p))

    def testRequestAvatarId(self):
        dbfile = self.mktemp()
        db = checkers.FilePasswordDB(dbfile, caseSensitive=0)
        f = file(dbfile, 'w')
        for (u, p) in self.users:
            f.write('%s:%s\n' % (u, p))
        f.close()

        for (u, p) in self.users:
            c = credentials.UsernamePassword(u, p)
            d = defer.maybeDeferred(db.requestAvatarId, c)
            self.assertEquals(unittest.deferredResult(d), u)

        for (u, p) in self.users:
            self.assertEquals(
                unittest.deferredResult(db.requestAvatarId(
                    credentials.UsernameHashedPassword(u, p))),
                u
            )

    def testHashedPasswords(self):
        def hash(u, p, s):
            return crypt(p, s)

        dbfile = self.mktemp()
        db = checkers.FilePasswordDB(dbfile, hash=hash)
        f = file(dbfile, 'w')
        for (u, p) in self.users:
            f.write('%s:%s\n' % (u, crypt(p, u[:2])))
        f.close()

        r = TestRealm()
        port = portal.Portal(r)
        port.registerChecker(db)

        for (u, p) in self.users:
            c = credentials.UsernamePassword(u, p)

            d = defer.maybeDeferred(db.requestAvatarId, c)
            self.assertEquals(unittest.deferredResult(d), u)

            d = port.login(c, None, ITestable)
            i, a, l = unittest.deferredResult(d)
            self.assertEquals(a.original.name, u)

            # It should fail if we pass the wrong password
            c = credentials.UsernamePassword(u, 'wrong password')
            d = port.login(c, None, ITestable)
            f = unittest.deferredError(d)
            f.trap(error.UnauthorizedLogin)

            # And it should fail for UsernameHashedPassword
            c = credentials.UsernameHashedPassword(u, crypt(p, u[:2]))
            d = port.login(c, None, ITestable)
            f = unittest.deferredError(d)
            f.trap(error.UnhandledCredentials)

    if crypt is None:
        testHashedPasswords.skip = "crypt module not available"

class PluggableAuthenticationModulesTest(unittest.TestCase):
    
    def setUpClass(self):
        self._oldCallIntoPAM = pamauth.callIntoPAM
        pamauth.callIntoPAM = self.callIntoPAM

    def tearDownClass(self):
        pamauth.callIntoPAM = self._oldCallIntoPAM

    def callIntoPAM(self, service, user, conv):
        if service != 'Twisted':
            raise error.UnauthorizedLogin('bad service: %s' % service)
        if user != 'testuser':
            raise error.UnauthorizedLogin('bad username: %s' % user)
        questions = [
                (1, "Password"),
                (2, "Message w/ Input"),
                (3, "Message w/o Input"),
                ]
        replies = conv(questions)
        if replies != [
            ("password", 0),
            ("entry", 0),
            ("", 0)
            ]:
                raise error.UnauthorizedLogin('bad conversion: %s' % repr(replies))
        return 1

    def _makeConv(self, d):
        def conv(questions):
            return defer.succeed([(d[t], 0) for t, q in questions])
        return conv

    def testRequestAvatarId(self):
        db = checkers.PluggableAuthenticationModulesChecker()
        conv = self._makeConv({1:'password', 2:'entry', 3:''})
        creds = credentials.PluggableAuthenticationModules('testuser',
                conv)
        d = db.requestAvatarId(creds)
        self.assertEquals(unittest.deferredResult(d), 'testuser')

    def testBadCredentials(self):
        db = checkers.PluggableAuthenticationModulesChecker()
        conv = self._makeConv({1:'', 2:'', 3:''})
        creds = credentials.PluggableAuthenticationModules('testuser',
                conv)
        d = db.requestAvatarId(creds)
        f = unittest.deferredError(d)
        f.trap(error.UnauthorizedLogin)

    def testBadUsername(self):
        db = checkers.PluggableAuthenticationModulesChecker()
        conv = self._makeConv({1:'password', 2:'entry', 3:''})
        creds = credentials.PluggableAuthenticationModules('baduser',
                conv)
        d = db.requestAvatarId(creds)
        f = unittest.deferredError(d)
        f.trap(error.UnauthorizedLogin)

    if not pamauth:
        skip = "Can't run without PyPAM"

class CheckersMixin:
    def testPositive(self):
        for chk in self.getCheckers():
            for (cred, avatarId) in self.getGoodCredentials():
                r = wFD(chk.requestAvatarId(cred))
                yield r
                self.assertEquals(r.getResult(), avatarId)
    testPositive = dG(testPositive)

    def testNegative(self):
        for chk in self.getCheckers():
            for cred in self.getBadCredentials():
                r = wFD(chk.requestAvatarId(cred))
                yield r
                self.assertRaises(error.UnauthorizedLogin, r.getResult)
        # Work around deferredGenerator bug
        yield None
    testNegative = dG(testNegative)

class HashlessFilePasswordDBMixin:
    credClass = credentials.UsernamePassword
    diskHash = None
    networkHash = staticmethod(lambda x: x)

    _validCredentials = [
        ('user1', 'password1'),
        ('user2', 'password2'),
        ('user3', 'password3')]

    def getGoodCredentials(self):
        for u, p in self._validCredentials:
            yield self.credClass(u, self.networkHash(p)), u

    def getBadCredentials(self):
        for u, p in [('user1', 'password3'),
                     ('user2', 'password1'),
                     ('bloof', 'blarf')]:
            yield self.credClass(u, self.networkHash(p))

    def getCheckers(self):
        diskHash = self.diskHash or (lambda x: x)
        hashCheck = self.diskHash and (lambda username, password, stored: self.diskHash(password))

        for cache in True, False:
            fn = self.mktemp()
            fObj = file(fn, 'w')
            for u, p in self._validCredentials:
                fObj.write('%s:%s\n' % (u, diskHash(p)))
            fObj.close()
            yield checkers.FilePasswordDB(fn, cache=cache, hash=hashCheck)

            fn = self.mktemp()
            fObj = file(fn, 'w')
            for u, p in self._validCredentials:
                fObj.write('%s dingle dongle %s\n' % (diskHash(p), u))
            fObj.close()
            yield checkers.FilePasswordDB(fn, ' ', 3, 0, cache=cache, hash=hashCheck)

            fn = self.mktemp()
            fObj = file(fn, 'w')
            for u, p in self._validCredentials:
                fObj.write('zip,zap,%s,zup,%s\n' % (u.title(), diskHash(p)))
            fObj.close()
            yield checkers.FilePasswordDB(fn, ',', 2, 4, False, cache=cache, hash=hashCheck)

class LocallyHashedFilePasswordDBMixin(HashlessFilePasswordDBMixin):
    diskHash = staticmethod(lambda x: x.encode('hex'))

class NetworkHashedFilePasswordDBMixin(HashlessFilePasswordDBMixin):
    networkHash = staticmethod(lambda x: x.encode('hex'))
    class credClass(credentials.UsernameHashedPassword):
        def checkPassword(self, password):
            return self.hashed.decode('hex') == password

class HashlessFilePasswordDBCheckerTestCase(HashlessFilePasswordDBMixin, CheckersMixin, unittest.TestCase):
    pass

class LocallyHashedFilePasswordDBCheckerTestCase(LocallyHashedFilePasswordDBMixin, CheckersMixin, unittest.TestCase):
    pass

class NetworkHashedFilePasswordDBCheckerTestCase(NetworkHashedFilePasswordDBMixin, CheckersMixin, unittest.TestCase):
    pass
