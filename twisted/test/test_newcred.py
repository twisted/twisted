
"""
Now with 30% more starch.
"""

from twisted.trial import unittest
from twisted.cred import portal, checkers, credentials, error
from twisted.python import components

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
