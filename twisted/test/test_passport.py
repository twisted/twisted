
from pyunit import unittest
from types import *
from twisted.internet import app, passport


EXCLUDE_FROM_BIGSUITE="Incapable test author."

class ForeignObject:
    "A strange object which shouldn't rightly be accepted by anything."

    def __init__(self, s=None):
        self.desc = s
        self.__setattr__ = self.x__setattr__

    def x__setattr__(self, key, value):
        raise TypeError, "I am read-only."

    def __repr__(self):
        s = "<ForeignObject at %s: %s>" % (id(self), self.desc)
        return s

    def __str__(self):
        raise TypeError,\
              'I do not have a meaningful string representation'\
              'like "%s".' % (self.desc,)

    def __hash__(self):
        raise TypeError, "unhashable type"

class Stubby:
    def __getattr__(self, key):
        raise KeyError, \
              "Stub %s doesn't have key %s.\n"\
              "An oversight of the unittester?" % (self.__class__, key)

# Service

class AppForServiceTest(Stubby, app.Application):
    def __init__(self, name, *a, **kw):
        self.name = name
        self.services = {}

class ServiceTestCase(unittest.TestCase):
    App = AppForServiceTest
    def setUp(self):
        self.service = passport.Service("test service")

    def testConstruction(self):
        app = self.App("test app for service-test")
        passport.Service("test service")
        passport.Service("test service", app)

    def testConstruction_serviceName(self):
        """serviceName is frequently used as a key, thus it is expected
        to be hashable."""

        self.assertRaises(TypeError, passport.Service,
                          ForeignObject("Not a Name"))

    def testConstruction_application(self):
        """application, if provided, should look at least vaugely like
        an application."""

        self.assertRaises(TypeError, passport.Service,
                          "test service",
                          ForeignObject("Not an Application"))

    def testsetApplication(self):
        appl = self.App("test app for service-test")
        self.service.setApplication(appl)
        self.assert_(self.service.application is appl)

    def testsetApplication_invalid(self):
        "setApplication should not accept bogus argument."

        self.assertRaises(TypeError, self.service.setApplication,
                          ForeignObject("Not an Application"))

    def testsetApplication_again(self):
        "setApplication should bail if already set."

        app1 = self.App("test app for service-test")
        app2 = self.App("another app?")
        self.service.setApplication(app1)
        self.assertRaises(AssertationError, self.service.setApplication,
                          app2)

    def testaddPerspective(self):
        p = passport.Perspective("perspective for service-test")
        self.service.addPerspective(p)

    def testgetPerspective(self):
        pname = "perspective for service-test"
        p = passport.Perspective(pname)
        self.service.addPerspective(p)
        self.service.getPerspective(pname)

    def testGetSetPerspetiveSanity(self):
        # XXX OBSOLETE
        pname = "perspective for service-test"
        p = passport.Perspective(pname)
        self.service.addPerspective(p)
        q = self.service.getPerspectiveNamed(pname)
        self.assertEqual(pname, q.getPerspectiveName())
        self.assertEqual(p,q)

    def testaddPerspective_invalid(self):
        self.assertRaises(TypeError, self.service.addPerspective,
                          ForeignObject("Not a Perspective"))

    def testgetPerspectiveNamed_invalid(self):
        # XXX OBSOLETE
        self.assertRaises(KeyError, self.service.getPerspectiveNamed,
                          "NoSuchPerspectiveNameAsThis")

    def testgetServiceName(self):
        self.assert_(self.service.getServiceName())

    def testgetServiceName_hashable(self):
        d = {}
        d[self.service.getServiceName()] = "value keyed to serviceName"

    def testgetServiceType(self):
        self.assert_(isinstance(self.service.getServiceType(),
                                StringType),
                     "ServiceType claimed to be a string, but isn't now.")


# Perspectives

class AppForPerspectiveTest(Stubby, app.Application):
    def __init__(self, name, *a, **kw):
        self.name = name
        self.authorizer = "Stub depth exceeded"

class ServiceForPerspectiveTest(Stubby, passport.Service):
    def __init__(self, name, appl):
        self.serviceName = name
        self.application = appl
        self.perspectives = {}

class IdentityForPerspectiveTest(Stubby, passport.Identity):
    def __init__(self, name, appl=None):
        self.name = name
        self.application = appl
        self.keyring = {}

class PerspectiveTestCase(unittest.TestCase):
    App = AppForPerspectiveTest
    Service = ServiceForPerspectiveTest
    Identity = IdentityForPerspectiveTest

    def setUp(self):
        self.app = self.App("app for perspective-test")
        self.service = self.Service("service for perspective-test",
                                    self.app)
        self.perspective = passport.Perspective("test perspective")


    def testConstruction(self):
        passport.Perspective("test perspective")
        passport.Perspective("test perspective", "testIdentityName")

    def testConstruction_invalidPerspectiveName(self):
        self.assertRaises(TypeError, passport.Perspective,
                          ForeignObject("Not a perspectiveName"),
                          self.service)

    def testConstruction_invalidService(self):
        self.assertRaises(TypeError, passport.Perspective,
                          "test perspective",
                          ForeignObject("Not a Service"))

    def testConstruction_invalidIdentityName(self):
        self.assertRaises(TypeError, passport.Perspective,
                          "test perspective", self.service,
                          ForeignObject("Not an idenityName"))

    def testsetIdentityName(self):
        self.perspective.setIdentityName("saneIdentityName")
        self.assertEqual(self.perspective.identityName,
                         "saneIdentityName")

    def testsetIdentityName_invalid(self):
        self.assertRaises(TypeError,
                          self.perspective.setIdentityName,
                          ForeignObject("unusable identityName"))

    def testsetIdentity(self):
        i = self.Identity("id test name")
        self.perspective.setIdentity(i)
        self.assertEqual(self.perspective.identityName, "id test name")

    def testsetIdentity_invalid(self):
        self.assertRaises(TypeError,
                          self.perspective.setIdentity,
                          ForeignObject("not an Identity"))

    def testmakeIdentity(self):
        self.perspective.makeIdentity("password")
        self.perspective.makeIdentity(None)

    def testmakeIdentity_invalid(self):
        self.assertRaises(TypeError, self.perspective.makeIdentity,
                          ForeignObject("Illegal Passkey"))

    def testmakeIdentity_exists(self):
        """Does the identity added by makeIdentity actually exist?"""

        raise NotImplementedError, "Um.  How do I do an async unit-test?"

    def testmakeIdentity_password(self):
        """Is the newly created identity's password correct?"""

        raise NotImplementedError, "Um.  How do I do an async unit-test?"

    def testgetPerspectiveName(self):
        name = self.perspective.getPerspectiveName()
        # self.assert_(
        #    self.service.getPerspectiveNamed(name) is self.perspective)

    def testgetService(self):
        s = self.perspective.getService()
        self.assert_(s is self.service)

    def testgetIdentityRequest(self):
        i = self.perspective.getIdentityRequest()
        # XXX - is the return value sane?

    def testattached(self):
        raise NotImplementedError, \
              "Kevin doesn't know enough to write this test."

    def testdetached(self):
        raise NotImplementedError, \
              "Kevin doesn't know enough to write this test."


class FunctionsTestCase(unittest.TestCase):
    def test_challenge(self):
        self.assert_(passport.challenge())

    def test_response(self):
        raise NotImplementedError

# Identity

class AppForIdentityTest(Stubby, app.Application):
    def __init__(self, name, *a, **kw):
        self.name = name
        self.authorizer = "Stub depth exceeded"

class ServiceForIdentityTest(Stubby, passport.Service):
    def __init__(self, name, appl):
        self.serviceName = name
        self.application = appl
        self.perspectives = {}

    def getServiceName(self):
        return self.serviceName

class PerspectiveForIdentityTest(Stubby, passport.Perspective):
    def __init__(self, name, service, *a, **kw):
        self.perspectiveName = name
        self.service = service

    def getService(self):
        return self.service

    def getPerspectiveName(self):
        return self.perspectiveName

class IdentityTestCase(unittest.TestCase):
    App = AppForIdentityTest
    Service = ServiceForIdentityTest
    Perspective = PerspectiveForIdentityTest

    def setUp(self):
        self.app = self.App("app for identity-test")
        self.ident = passport.Identity("test identity", self.app)

    def testConstruction(self):
        passport.Identity("test name", self.app)

    def testConstruction_invalidApp(self):
        self.assertRaises(TypeError, passport.Identity,
                          "test name", ForeignObject("not an app"))

    def test_addKeyByString(self):
        self.ident.addKeyByString("one", "two")
        self.assert_(("one", "two") in self.ident.getAllKeys())

    def test_addKeyForPerspective(self):
        service = self.Service("one", self.app)
        perspective = self.Perspective("two")

        self.ident.addKeyForPerspective(perspective)
        self.assert_(("one", "two") in self.ident.getAllKeys())

    def test_getAllKeys(self):
        self.assert_(len(self.ident.getAllKeys()) == 0)

        service = self.Service("one", self.app)

        for n in ("p1","p2","p3"):
            perspective = self.Perspective(n)
            self.ident.addKeyForPerspective(perspective)

        keys = self.ident.getAllKeys()

        self.assertEqual(keys, 3)

        for n in ("p1","p2","p3"):
            self.assert_(("one", n) in keys)

    def test_removeKey(self):
        self.ident.addKeyByString("one", "two")
        self.ident.removeKey("one", "two")
        self.assert_(len(self.ident.getAllKeys()) == 0)

    def test_removeKey_invalid(self):
        self.assertRaises(KeyError, self.ident.removeKey,
                          "never","was")

    def test_setPassword(self):
        self.ident.setPassword("passphrase")

    def test_setPassword_invalid(self):
        self.assertRaises(TypeError, self.ident.setPassword,
                          ForeignObject("not a valid passphrase"))

    def test_challenge(self):
        self.assert_(self.ident.challenge())
        # XXX - test result?

    def test_verifyPassword(self):
        self.ident.setPassword("passphrase")
        self.assert_(not self.ident.verifyPassword("wr", "ong"))
        raise NotImplementedError, "Blerg, eat kitty."

    def test_verifyPlainPassword(self):
        self.ident.setPassword("passphrase")
        self.assert_(self.ident.verifyPlainPassword("passphrase"))
        self.assert_(not self.ident.verifyPlainPassword("wrongphrase"))


class AuthorizerTestCase(unittest.TestCase):
    """XXX - TestCase for passport.DefaultAuthorizer not yet written."""
    pass

if __name__ == "__main__":
    unittest.main()
