from twisted.trial import unittest
from twisted.internet import defer
from twisted.cred import error
from twisted.web2.auth import basic, digest, wrapper
from twisted.web2.test.test_server import SimpleRequest

from twisted.web2.test import test_server

import base64

class FakeDigestCredentialFactory(digest.DigestCredentialFactory):
    def generateNonce(self):
        return '178288758716122392881254770685'

    def generateOpaque(self):
        return '1041524039'

class BasicAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.credentialFactory = basic.BasicCredentialFactory('foo')
        self.username = 'dreid'
        self.password = 'S3CuR1Ty'

    def testUsernamePassword(self):
        response = base64.encodestring('%s:%s' % (
                self.username,
                self.password))

        creds = self.credentialFactory.decode(response, _trivial_GET)
        self.failUnless(creds.checkPassword(self.password))

    def testIncorrectPassword(self):
        response = base64.encodestring('%s:%s' % (
                self.username,
                'incorrectPassword'))

        creds = self.credentialFactory.decode(response, _trivial_GET)
        self.failIf(creds.checkPassword(self.password))

    def testIncorrectPadding(self):
        response = base64.encodestring('%s:%s' % (
                self.username,
                self.password))

        response = response.strip('=')

        creds = self.credentialFactory.decode(response, _trivial_GET)
        self.failUnless(creds.checkPassword(self.password))

    def testInvalidCredentials(self):
        response = base64.encodestring(self.username)

        self.assertRaises(error.LoginFailed, 
                          self.credentialFactory.decode, 
                          response, _trivial_GET)

challengeResponse = ('digest', {'nonce': '178288758716122392881254770685', 
                                'qop': 'auth', 'realm': 'test realm', 
                                'algorithm': 'md5', 'opaque': '1041524039'})

authRequest = 'username="username", realm="test realm", nonce="178288758716122392881254770685", uri="/write/", response="62f388be1cf678fbdfce87910871bcc5", opaque="1041524039", algorithm="md5", cnonce="29fc54aa1641c6fa0e151419361c8f23", nc=00000001, qop="auth"'

namelessAuthRequest = 'realm="test realm",nonce="doesn\'t matter"'

class DigestAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.credentialFactory = FakeDigestCredentialFactory('md5', 
                                                             'test realm')

    def testGetChallenge(self):
        self.assertEquals(
            self.credentialFactory.getChallenge(None),
            challengeResponse[1])

    def testResponse(self):
        challenge = self.credentialFactory.getChallenge(None)

        creds = self.credentialFactory.decode(authRequest, _trivial_GET)
        self.failUnless(creds.checkPassword('password'))

    def testFailsWithDifferentMethod(self):
        challenge = self.credentialFactory.getChallenge(None)
        
        creds = self.credentialFactory.decode(authRequest, SimpleRequest(None, 'POST', '/'))
        self.failIf(creds.checkPassword('password'))

    def testNoUsername(self):
        self.assertRaises(error.LoginFailed, self.credentialFactory.decode, namelessAuthRequest, _trivial_GET)

from zope.interface import Interface, implements
from twisted.cred import portal, checkers

class ITestHTTPUser(Interface):
    pass

class TestHTTPUser(object):
    implements(ITestHTTPUser)

class TestAuthRealm(object):
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if ITestHTTPUser in interfaces:
            return ITestHTTPUser, TestHTTPUser()

        raise NotImplementedError("Only ITestHTTPUser interface is supported")

class HTTPAuthResourceTest(test_server.BaseCase):
    def setUp(self):
        self.portal = portal.Portal(TestAuthRealm())
        c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        c.addUser('username', 'password')

        self.portal.registerChecker(c)

        self.credFactory = basic.BasicCredentialFactory('test realm')

        self.protectedResource = test_server.BaseTestResource()
        self.protectedResource.responseText = "You shouldn't see me."

    def tearDown(self):
        del self.portal
        del self.credFactory
        del self.protectedResource

    def testUnauthorizedResponse(self):
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(ITestHTTPUser,))

        def makeDeepRequest(res):
            return self.assertResponse((root,
                                        'http://localhost/foo/bar/baz/bax'),
                                       (401,
                                        {'WWW-Authenticate': [('basic',
                                                               {'realm': "test realm"})]},
                                        None))

        d = self.assertResponse((root, 'http://localhost/'),
                                (401, 
                                 {'WWW-Authenticate': [('basic', 
                                                        {'realm': "test realm"})]},
                                 None))
        
        return d.addCallback(makeDeepRequest)

    def testBadCredentials(self):
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(ITestHTTPUser,))

        credentials = base64.encodestring('bad:credentials')

        d = self.assertResponse((root, 'http://localhost/', 
                                 {'authorization': [('basic', credentials)]}),
                                (401,
                                 {'WWW-Authenticate': [('basic',
                                                        {'realm': "test realm"})]},
                                 None))

        return d
    
    def testSuccessfulLogin(self):
        self.protectedResource.responseText = "I hope you can see me."

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(ITestHTTPUser,))

        credentials = base64.encodestring('username:password')

        d = self.assertResponse((root, 'http://localhost/',
                                 {'authorization': ('basic', credentials)}),
                                (200,
                                 {}, 'I hope you can see me.'))

        return d

    def testWrongScheme(self):
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(ITestHTTPUser,))

        d = self.assertResponse((root, 'http://localhost/',
                                 {'authorization': 
                                  [('digest', 
                                    'realm="foo", response="crap"')]}),
                                (401,
                                 {'www-authenticate': 
                                  [('basic', {'realm': 'test realm'})]},
                                 None))

        return d

    def testMultipleWWWAuthenticateSchemes(self):
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        (basic.BasicCredentialFactory('test realm'),
                                         FakeDigestCredentialFactory('md5', 'test realm')),
                                        self.portal,
                                        interfaces=(ITestHTTPUser,))

        d = self.assertResponse((root, 'http://localhost/', {}),
                                (401,
                                 {'www-authenticate':
                                  [challengeResponse,
                                   ('basic', {'realm': 'test realm'})]},
                                 None))

        return d

    def testAuthorizationAgainstMultipleSchemes(self):
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        (basic.BasicCredentialFactory('test realm'),
                                         FakeDigestCredentialFactory('md5', 'test realm')),
                                        self.portal,
                                        interfaces=(ITestHTTPUser,))

        def respond(ign):
            d = self.assertResponse((root, 'http://localhost/',
                                     {'authorization': authRequest}),
                                    (200,
                                     {},
                                     None))
            return d

        d = self.assertResponse((root, 'http://localhost/', {}),
                                (401,
                                 {'www-authenticate':
                                  [challengeResponse,
                                   ('basic', {'realm': 'test realm'})]},
                                 None))

        return d

_trivial_GET = SimpleRequest(None, 'GET', '/')
