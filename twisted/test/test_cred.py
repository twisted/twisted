
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

import sys
from twisted.trial import unittest
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


# Service
AppForServiceTest = app.Application

class ServiceTestCase(unittest.TestCase):
    App = AppForServiceTest

    def setUp(self):
        self.service = service.Service("test service", authorizer=authorizer.Authorizer())

    def testConstruction(self):
        appl = self.App("test app for service-test")
        auth = authorizer.Authorizer()
        parent = app.MultiService("test")
        service.Service("test service")
        service.Service("test service", authorizer=auth)
        service.Service("test service", parent)

    def testParent(self):
        parent = app.MultiService("test")
        auth = authorizer.Authorizer(parent)
        s = service.Service("test service", parent, authorizer=auth)
        self.assertEqual(s.authorizer.getServiceNamed(s.getServiceName()),
                         s)
        parent2 = app.MultiService("test")
        s.disownServiceParent()
        s.setServiceParent(parent2)
        self.assertEqual(s.authorizer.getServiceNamed(s.getServiceName()),
                         s)
 

    def testConstruction_serviceName(self):
        """serviceName is frequently used as a key, thus it is expected
        to be hashable."""

        self.assertRaises(TypeError, service.Service,
                          ForeignObject("Not a Name"))

    def testsetServiceParent(self):
        parent = app.MultiService("test")
        self.service.setServiceParent(parent)
        self.assert_(self.service.serviceParent is parent)

##    def testsetApplication_invalid(self):
##        "setApplication should not accept bogus argument."

##        self.assertRaises(TypeError, self.service.setApplication,
##                          ForeignObject("Not an Application"))

##    def testsetApplication_again(self):
##        "setApplication should bail if already set."

##        app1 = self.App("test app for service-test")
##        app2 = self.App("another app?")
##        self.service.setApplication(app1)
##        self.assertRaises(RuntimeError, self.service.setApplication,
##                          app2)

    def testgetPerspective(self):
        self.pname = pname = "perspective for service-test"
        self.p = p = perspective.Perspective(pname)
        self.service.addPerspective(p)
        d = self.service.getPerspectiveRequest(pname)
        d.addCallback(self._checkPerspective)

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

AppForPerspectiveTest = app.Application
ServiceForPerspectiveTest = service.Service
IdentityForPerspectiveTest = identity.Identity

class PerspectiveTestCase(unittest.TestCase):
    App = AppForPerspectiveTest
    Service = ServiceForPerspectiveTest
    def Identity(self, n):
        return self.auth.createIdentity(n)


    def setUp(self):
        self.app = self.App("app for perspective-test")
        self.auth = authorizer.DefaultAuthorizer()
        self.service = self.Service("service for perspective-test",
                                    authorizer=self.auth)
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
        i.setPassword("")
        pwrq = i.verifyPassword("foo", "bar")
        pwrq.addErrback(self._identityWithNoPassword_fail)

    def _identityWithNoPassword_fail(self, msg):
        # "Identity with no password did not authenticate."
        pass

    def test_identityWithNoPassword_plain(self):
        i = self.Identity("id test name")
        pwrq = i.verifyPlainPassword("foo")
        pwrq.addErrback(self._identityWithNoPassword_plain_fail)

    def _identityWithNoPassword_plain_fail(self, msg):
        # "Identity with no password did not authenticate (plaintext): %s"
        pass

    def testsetIdentity_invalid(self):
        self.assertRaises(TypeError,
                          self.perspective.setIdentity,
                          ForeignObject("not an Identity"))

    def testmakeIdentity(self):
        self.ident = ident = self.perspective.makeIdentity("password")
        # simple password verification
        pwrq = ident.verifyPlainPassword("password")
        pwrq.addCallbacks(self._testmakeIdentity_1, self._testmakeIdentity_1fail)

    def _testmakeIdentity_1fail(self, msg):
        try:
            self.fail("Identity did not verify with plain password: %s" % msg)
        except self.failureException, e:
            self.error = sys.exc_info()
            raise

    def _testmakeIdentity_1(self, msg):
        # complex password verification
        ident = self.ident
        challenge = ident.challenge()
        hashedPassword = util.respond(challenge, "password")
        pwrq = ident.verifyPassword(challenge, hashedPassword)
        pwrq.addCallback(self._testmakeIdentity_2)
        pwrq.addErrback(self._testmakeIdentity_2fail)

    def _testmakeIdentity_2fail(self, msg):
        try:
            self.fail("Identity did not verify with hashed password: %s" % msg)
        except self.failureException, e:
            self.error = sys.exc_info()
            raise

    def _testmakeIdentity_2(self, msg):
        d = self.perspective.getIdentityRequest()
        d.addCallback(self._gotIdentity)

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

AppForIdentityTest = AppForPerspectiveTest

ServiceForIdentityTest = ServiceForPerspectiveTest

class PerspectiveForIdentityTest(perspective.Perspective):
    def __init__(self, n, service):
        perspective.Perspective.__init__(self, n)
        self.setService(service)

class IdentityTestCase(unittest.TestCase):
    App = AppForIdentityTest
    Service = ServiceForIdentityTest
    Perspective = PerspectiveForIdentityTest

    def setUp(self):
        self.auth = authorizer.DefaultAuthorizer()
        self.ident = identity.Identity("test identity", authorizer=self.auth)

    def testConstruction(self):
        identity.Identity("test name", authorizer=self.auth)

    def test_addKeyByString(self):
        self.ident.addKeyByString("one", "two")
        self.assert_(("one", "two") in self.ident.getAllKeys())

    def test_addKeyForPerspective(self):
        service = self.Service("one", authorizer=self.auth)
        perspective = self.Perspective("two", service)

        self.ident.addKeyForPerspective(perspective)
        self.assert_(("one", "two") in self.ident.getAllKeys())

    def test_getAllKeys(self):
        self.assert_(len(self.ident.getAllKeys()) == 0)

        service = self.Service("one", authorizer=self.auth)

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

        self._test_verifyPassword_worked = 0
        pwrq = self.ident.verifyPassword("wr", "ong")
        pwrq.addCallback(self._test_verifyPassword_false_pos)
        pwrq.addErrback(self._test_verifyPassword_correct_neg)
        # the following test actually needs the identity in testing
        # to have sync password checking..
        self.assert_(self._test_verifyPassword_worked)

    def _test_verifyPassword_false_pos(self, msg):
        self.fail("Identity accepted invalid hashed password")

    def _test_verifyPassword_correct_neg(self, msg):
        self.assert_(self._test_verifyPassword_worked==0)
        self._test_verifyPassword_worked = 1

    def test_verifyPlainPassword(self):
        self.ident.setPassword("passphrase")

        self._test_verifyPlainPassword_worked = 0

        pwrq1 = self.ident.verifyPlainPassword("passphrase")
        pwrq1.addErrback(self._test_verifyPlainPassword_fail)
        pwrq1.addCallback(self._test_verifyPlainPassword_ok)
        self.assert_(self._test_verifyPlainPassword_worked==1)

        pwrq2 = self.ident.verifyPlainPassword("wrongphrase")
        pwrq2.addCallback(self._test_verifyPlainPassword_false_pos)
        pwrq2.addErrback(self._test_verifyPlainPassword_correct_neg)
        self.assert_(self._test_verifyPlainPassword_worked==2)

    def _test_verifyPlainPassword_fail(self, msg):
        self.fail("Identity did not verify with plain password")

    def _test_verifyPlainPassword_ok(self, msg):
        self.assert_(self._test_verifyPlainPassword_worked==0)
        self._test_verifyPlainPassword_worked = 1

    def _test_verifyPlainPassword_false_pos(self, msg):
        self.fail("Identity accepted invalid plain password")

    def _test_verifyPlainPassword_correct_neg(self, msg):
        self.assert_(self._test_verifyPlainPassword_worked==1)
        self._test_verifyPlainPassword_worked = 2



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
        i = identity.Identity("user", self.auth)

        # add the identity
        self.auth.addIdentity(i)
        self.assertRaises(KeyError, self.auth.addIdentity, i)
        self.assert_(self.auth.identities.has_key("user"))

        # get request for identity
        self.ident = i
        d = self.auth.getIdentityRequest("user")
        d.addCallback(self._gotIdentity).addErrback(self._error)

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
