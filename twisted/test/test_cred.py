
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
Tests for twisted.cred.
"""

from pyunit import unittest
from types import *
from twisted.internet import app
from twisted.cred import authorizer, identity, perspective, service, util


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
        self.service = service.Service("test service")

    def testConstruction(self):
        app = self.App("test app for service-test")
        service.Service("test service")
        service.Service("test service", app)

    def testConstruction_serviceName(self):
        """serviceName is frequently used as a key, thus it is expected
        to be hashable."""

        self.assertRaises(TypeError, service.Service,
                          ForeignObject("Not a Name"))

    def testConstruction_application(self):
        """application, if provided, should look at least vaugely like
        an application."""

        self.assertRaises(TypeError, service.Service,
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
        self.assertRaises(RuntimeError, self.service.setApplication,
                          app2)

    def testgetPerspective(self):
        self.pname = pname = "perspective for service-test"
        self.p = p = perspective.Perspective(pname)
        self.service.addPerspective(p)
        d = self.service.getPerspectiveRequest(pname)
        d.addCallback(self._checkPerspective)
        d.arm()
    
    def _checkPerspective(self, q):
        self.assertEquals(self.p, q)
        self.assertEquals(self.pname, q.getPerspectiveName())
        del self.p
        del self.pname

    def testGetSetPerspetiveSanity(self):
        # XXX OBSOLETE
        pname = "perspective for service-test"
        p = perspective.Perspective(pname)
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
        self.authorizer = authorizer.DefaultAuthorizer()
        self.authorizer.setApplication(self)

class ServiceForPerspectiveTest(Stubby, service.Service):
    def __init__(self, name, appl):
        self.serviceName = name
        self.application = appl
        self.perspectives = {}

class IdentityForPerspectiveTest(Stubby, identity.Identity):
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
        self.perspective = perspective.Perspective("test perspective")
        self.perspective.setService(self.service)

    def testConstruction(self):
        perspective.Perspective("test perspective")
        perspective.Perspective("test perspective", "testIdentityName")

    def testConstruction_invalidPerspectiveName(self):
        self.assertRaises(TypeError, perspective.Perspective,
                          ForeignObject("Not a perspectiveName"),
                          self.service)

    def testConstruction_invalidService(self):
        self.assertRaises(TypeError, perspective.Perspective,
                          "test perspective",
                          ForeignObject("Not a Service"))

    def testConstruction_invalidIdentityName(self):
        self.assertRaises(TypeError, perspective.Perspective,
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

    def test_identityWithNoPassword(self):
        i = self.Identity("id test name")
        self.assert_(not i.verifyPassword("foo", "bar"))
        self.assert_(not i.verifyPlainPassword("foo"))
    
    def testsetIdentity_invalid(self):
        self.assertRaises(TypeError,
                          self.perspective.setIdentity,
                          ForeignObject("not an Identity"))

    def testmakeIdentity(self):
        self.ident = ident = self.perspective.makeIdentity("password")
        # simple password verification
        self.assert_(ident.verifyPlainPassword("password"))
        
        # complex password verification
        challenge = ident.challenge()
        hashedPassword = util.respond(challenge, "password")
        self.assert_(ident.verifyPassword(challenge, hashedPassword))
        
        d = self.perspective.getIdentityRequest()
        d.addCallback(self._gotIdentity)
        d.arm()
    
    def _gotIdentity(self, ident):
        self.assertEquals(self.ident, ident)
        del self.ident
        
    def testmakeIdentity_invalid(self):
        self.assertRaises(TypeError, self.perspective.makeIdentity,
                          ForeignObject("Illegal Passkey"))

    def testgetService(self):
        s = self.perspective.getService()
        self.assert_(s is self.service)

class FunctionsTestCase(unittest.TestCase):
    def test_challenge(self):
        self.assert_(identity.challenge())

class AppForIdentityTest(Stubby, app.Application):
    def __init__(self, name, *a, **kw):
        self.name = name
        self.authorizer = "Stub depth exceeded"

class ServiceForIdentityTest(Stubby, service.Service):
    def __init__(self, name, appl):
        self.serviceName = name
        self.application = appl
        self.perspectives = {}

    def getServiceName(self):
        return self.serviceName

class PerspectiveForIdentityTest(Stubby, perspective.Perspective):
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
        self.ident = identity.Identity("test identity", self.app)

    def testConstruction(self):
        identity.Identity("test name", self.app)

    def testConstruction_invalidApp(self):
        self.assertRaises(TypeError, identity.Identity,
                          "test name", ForeignObject("not an app"))

    def test_addKeyByString(self):
        self.ident.addKeyByString("one", "two")
        self.assert_(("one", "two") in self.ident.getAllKeys())

    def test_addKeyForPerspective(self):
        service = self.Service("one", self.app)
        perspective = self.Perspective("two", service)

        self.ident.addKeyForPerspective(perspective)
        self.assert_(("one", "two") in self.ident.getAllKeys())

    def test_getAllKeys(self):
        self.assert_(len(self.ident.getAllKeys()) == 0)

        service = self.Service("one", self.app)

        for n in ("p1","p2","p3"):
            perspective = self.Perspective(n, service)
            self.ident.addKeyForPerspective(perspective)

        keys = self.ident.getAllKeys()

        self.assertEqual(len(keys), 3)

        for n in ("p1","p2","p3"):
            self.assert_(("one", n) in keys)

    def test_removeKey(self):
        self.ident.addKeyByString("one", "two")
        self.ident.removeKey("one", "two")
        self.assert_(len(self.ident.getAllKeys()) == 0)

    def test_removeKey_invalid(self):
        self.assertRaises(KeyError, self.ident.removeKey,
                          "never","was")

    def test_setPassword_invalid(self):
        self.assertRaises(TypeError, self.ident.setPassword,
                          ForeignObject("not a valid passphrase"))

    def test_verifyPassword(self):
        self.ident.setPassword("passphrase")
        self.assert_(not self.ident.verifyPassword("wr", "ong"))

    def test_verifyPlainPassword(self):
        self.ident.setPassword("passphrase")
        self.assert_(self.ident.verifyPlainPassword("passphrase"))
        self.assert_(not self.ident.verifyPlainPassword("wrongphrase"))


class AuthorizerTestCase(unittest.TestCase):
    """TestCase for authorizer.DefaultAuthorizer."""
    
    def setUp(self):
        self.auth = authorizer.DefaultAuthorizer()
    
    def _error(self, e):
        raise RuntimeError, e
    
    def _gotIdentity(self, i):
        self.assertEquals(self.ident, i)
        del self.ident
    
    def test_addIdent(self):
        a = app.Application("test")
        i = identity.Identity("user", a)
        
        # add the identity
        self.auth.addIdentity(i)
        self.assertRaises(KeyError, self.auth.addIdentity, i)
        self.assert_(self.auth.identities.has_key("user"))
        
        # get request for identity
        self.ident = i
        d = self.auth.getIdentityRequest("user")
        d.addCallback(self._gotIdentity).addErrback(self._error)
        d.arm()
        
        # remove identity
        self.auth.removeIdentity("user")
        self.assert_(not self.auth.identities.has_key("user"))
        self.assertRaises(KeyError, self.auth.removeIdentity, "user")
        self.assertRaises(KeyError, self.auth.removeIdentity, "otheruser")
    
    def _gotNoUser(self, err):
        pass
    
    def test_nonExistentIdent(self):
        d = self.auth.getIdentityRequest("nosuchuser")
        d.addCallback(self._error).addErrback(self._gotNoUser)
        d.arm()


if __name__ == "__main__":
    unittest.main()
