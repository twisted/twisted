# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Now with 30% more starch.
"""

from twisted.trial import unittest
from twisted.cred import portal, checkers, credentials, error
from twisted.python import components
from twisted.python import util
from twisted.internet import defer

import hmac

try:
    from crypt import crypt
except ImportError:
    crypt = None

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
    __implements__ = ITestable

# components.Interface(TestAvatar).adaptWith(Testable, ITestable)

components.registerAdapter(Testable, TestAvatar, ITestable)

class TestRealm:
    __implements__ = portal.IRealm
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
        self.failUnless(components.implements(impl, iface),
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
        db = checkers.OnDiskUsernamePasswordDatabase(dbfile)
        f = file(dbfile, 'w')
        for (u, p) in self.users:
            f.write('%s:%s\n' % (u, p))
        f.close()

        for (u, p) in self.users:
            self.failUnlessRaises(KeyError, db.getUser, u.upper())
            self.assertEquals(db.getUser(u), (u, p))

    def testCaseInSensitivity(self):
        dbfile = self.mktemp()
        db = checkers.OnDiskUsernamePasswordDatabase(dbfile, caseSensitive=0)
        f = file(dbfile, 'w')
        for (u, p) in self.users:
            f.write('%s:%s\n' % (u, p))
        f.close()

        for (u, p) in self.users:
            self.assertEquals(db.getUser(u.upper()), (u, p))

    def testRequestAvatarId(self):
        dbfile = self.mktemp()
        db = checkers.OnDiskUsernamePasswordDatabase(dbfile, caseSensitive=0)
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
        db = checkers.OnDiskUsernamePasswordDatabase(dbfile, hash=hash)
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
