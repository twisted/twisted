from twisted.trial import unittest
from twisted.cred import error
from twisted.web2.auth import basic, digest, wrapper
from twisted.web2.auth.interfaces import IAuthenticatedRequest, IHTTPUser
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

from zope.interface import implements
from twisted.cred import portal, checkers

class TestHTTPUser(object):
    """
    Test avatar implementation for http auth with cred
    """
    implements(IHTTPUser)

    username = None

    def __init__(self, username):
        """
        @param username: The str username sent as part of the HTTP auth
            response.
        """
        self.username = username

class TestAuthRealm(object):
    """
    Test realm that supports the IHTTPUser interface
    """

    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IHTTPUser in interfaces:
            return IHTTPUser, TestHTTPUser(avatarId)

        raise NotImplementedError("Only IHTTPUser interface is supported")


class ProtectedResource(test_server.BaseTestResource):
    """
    A test resource for use with HTTPAuthWrapper that holds on to it's
    request and segments so we can assert things about them.
    """
    addSlash = True

    request = None
    segments = None

    def render(self, req):
        self.request = req
        return super(ProtectedResource, self).render(req)

    def locateChild(self, req, segments):
        self.segments = segments
        return super(ProtectedResource, self).locateChild(req, segments)


class HTTPAuthResourceTest(test_server.BaseCase):
    """
    Tests for the HTTPAuthWrapper Resource
    """

    def setUp(self):
        """
        Create a portal and add an in memory checker to it.

        Then set up a protectedResource that will be wrapped in each test.
        """
        self.portal = portal.Portal(TestAuthRealm())
        c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        c.addUser('username', 'password')

        self.portal.registerChecker(c)

        self.credFactory = basic.BasicCredentialFactory('test realm')

        self.protectedResource = ProtectedResource()
        self.protectedResource.responseText = "You shouldn't see me."

    def tearDown(self):
        """
        Clean up by getting rid of the portal, credentialFactory, and
        protected resource
        """
        del self.portal
        del self.credFactory
        del self.protectedResource

    def test_AuthenticatedRequest(self):
        """
        Test that after successful authentication the request provides
        IAuthenticatedRequest and that the request.avatar implements
        the proper interfaces for this realm and has the proper values
        for this request.
        """
        self.protectedResource.responseText = "I hope you can see me."

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        credentials = base64.encodestring('username:password')

        d = self.assertResponse((root, 'http://localhost/',
                                 {'authorization': ('basic', credentials)}),
                                (200,
                                 {}, 'I hope you can see me.'))

        def checkRequest(result):
            resource = self.protectedResource

            self.failUnless(hasattr(resource, "request"))

            request = resource.request

            self.failUnless(IAuthenticatedRequest.providedBy(request))
            self.failUnless(hasattr(request, "avatar"))
            self.failUnless(IHTTPUser.providedBy(request.avatar))
            self.failUnless(hasattr(request, "avatarInterface"))
            self.assertEquals(request.avatarInterface, IHTTPUser)
            self.assertEquals(request.avatar.username, 'username')

        d.addCallback(checkRequest)
        return d

    def test_AllowedMethods(self):
        """
        Test that unknown methods result in a 401 instead of a 405 when
        authentication hasn't been completed.
        """

        self.method = 'PROPFIND'

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))
        d = self.assertResponse((root, 'http://localhost/'),
                                (401,
                                 {'WWW-Authenticate': [('basic',
                                                        {'realm': "test realm"})]},
                                None))

        self.method = 'GET'

        return d

    def test_UnauthorizedResponse(self):
        """
        Test that a request with no credentials results in a
        valid Unauthorized response.
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

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

    def test_BadCredentials(self):
        """
        Test that a request with bad credentials results in a valid
        Unauthorized response
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        credentials = base64.encodestring('bad:credentials')

        d = self.assertResponse((root, 'http://localhost/',
                                 {'authorization': ('basic', credentials)}),
                                (401,
                                 {'WWW-Authenticate': [('basic',
                                                        {'realm': "test realm"})]},
                                 None))

        return d

    def test_SuccessfulLogin(self):
        """
        Test that a request with good credentials results in the
        appropriate response from the protected resource
        """
        self.protectedResource.responseText = "I hope you can see me."

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        credentials = base64.encodestring('username:password')

        d = self.assertResponse((root, 'http://localhost/',
                                 {'authorization': ('basic', credentials)}),
                                (200,
                                 {}, 'I hope you can see me.'))

        return d

    def test_WrongScheme(self):
        """
        Test that a request with credentials for a scheme that is not
        advertised by this resource results in the appropriate
        unauthorized response.
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        d = self.assertResponse((root, 'http://localhost/',
                                 {'authorization':
                                  [('digest',
                                    'realm="foo", response="crap"')]}),
                                (401,
                                 {'www-authenticate':
                                  [('basic', {'realm': 'test realm'})]},
                                 None))

        return d

    def test_MultipleWWWAuthenticateSchemes(self):
        """
        Test that our unauthorized response can contain challenges for
        multiple authentication schemes.
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        (basic.BasicCredentialFactory('test realm'),
                                         FakeDigestCredentialFactory('md5', 'test realm')),
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        d = self.assertResponse((root, 'http://localhost/', {}),
                                (401,
                                 {'www-authenticate':
                                  [challengeResponse,
                                   ('basic', {'realm': 'test realm'})]},
                                 None))

        return d

    def test_AuthorizationAgainstMultipleSchemes(self):
        """
        Test that we can authenticate to either authentication scheme.
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        (basic.BasicCredentialFactory('test realm'),
                                         FakeDigestCredentialFactory('md5', 'test realm')),
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        def respondBasic(ign):
            credentials = base64.encodestring('username:password')

            d = self.assertResponse((root, 'http://localhost/',
                                     {'authorization':
                                        ('basic', credentials)}),
                                    (200,
                                     {}, None))

            return d

        def respond(ign):
            d = self.assertResponse((root, 'http://localhost/',
                                     {'authorization': authRequest}),
                                    (200,
                                     {},
                                     None))
            return d.addCallback(respondBasic)

        d = self.assertResponse((root, 'http://localhost/', {}),
                                (401,
                                 {'www-authenticate':
                                  [challengeResponse,
                                   ('basic', {'realm': 'test realm'})]},
                                 None))

        return d

    def test_WrappedResourceGetsFullSegments(self):
        """
        Test that the wrapped resource gets all the URL segments in it's
        locateChild.
        """
        self.protectedResource.responseText = "I hope you can see me."

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        credentials = base64.encodestring('username:password')

        d = self.assertResponse((root, 'http://localhost/foo/bar/baz/bax',
                                 {'authorization': ('basic', credentials)}),
                                (404,
                                 {}, None))

        def checkSegments(ign):
            resource = self.protectedResource

            self.assertEquals(resource.segments, ['foo', 'bar', 'baz', 'bax'])

        d.addCallback(checkSegments)

        return d

    def test_InvalidCredentials(self):
        """
        Malformed or otherwise invalid credentials (as determined by
        the credential factory) should result in an Unauthorized response
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        credentials = base64.encodestring('Not Good Credentials')

        d = self.assertResponse((root, 'http://localhost/',
                                 {'authorization': ('basic', credentials)}),
                                (401,
                                 {'WWW-Authenticate': [('basic',
                                                        {'realm': "test realm"})]},
                                 None))

        return d


_trivial_GET = SimpleRequest(None, 'GET', '/')
