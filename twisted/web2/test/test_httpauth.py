# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python.hashlib import md5
from twisted.internet import address
from twisted.trial import unittest
from twisted.cred import error
from twisted.web2 import http, responsecode
from twisted.web2.auth import basic, digest, wrapper
from twisted.web2.auth.interfaces import IAuthenticatedRequest, IHTTPUser
from twisted.web2.test.test_server import SimpleRequest

from twisted.web2.test import test_server

import base64

class FakeDigestCredentialFactory(digest.DigestCredentialFactory):
    """
    A Fake Digest Credential Factory that generates a predictable
    nonce and opaque
    """

    def __init__(self, *args, **kwargs):
        super(FakeDigestCredentialFactory, self).__init__(*args, **kwargs)

        self.privateKey = "0"

    def generateNonce(self):
        """
        Generate a static nonce
        """
        return '178288758716122392881254770685'

    def _getTime(self):
        """
        Return a stable time
        """
        return 0


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


clientAddress = address.IPv4Address('TCP', '127.0.0.1', 80)

challengeOpaque = ('75c4bd95b96b7b7341c646c6502f0833-MTc4Mjg4NzU'
                   '4NzE2MTIyMzkyODgxMjU0NzcwNjg1LHJlbW90ZWhvc3Q'
                   'sMA==')

challengeNonce = '178288758716122392881254770685'

challengeResponse = ('digest',
                     {'nonce': challengeNonce,
                      'qop': 'auth', 'realm': 'test realm',
                      'algorithm': 'md5',
                      'opaque': challengeOpaque})

cnonce = "29fc54aa1641c6fa0e151419361c8f23"

authRequest1 = ('username="username", realm="test realm", nonce="%s", '
                'uri="/write/", response="%s", opaque="%s", algorithm="md5", '
                'cnonce="29fc54aa1641c6fa0e151419361c8f23", nc=00000001, '
                'qop="auth"')

authRequest2 = ('username="username", realm="test realm", nonce="%s", '
                'uri="/write/", response="%s", opaque="%s", algorithm="md5", '
                'cnonce="29fc54aa1641c6fa0e151419361c8f23", nc=00000002, '
                'qop="auth"')

namelessAuthRequest = 'realm="test realm",nonce="doesn\'t matter"'


class DigestAuthTestCase(unittest.TestCase):
    """
    Test the behavior of DigestCredentialFactory
    """

    def setUp(self):
        """
        Create a DigestCredentialFactory for testing
        """
        self.credentialFactory = digest.DigestCredentialFactory('md5',
                                                                'test realm')

    def getDigestResponse(self, challenge, ncount):
        """
        Calculate the response for the given challenge
        """
        nonce = challenge.get('nonce')
        algo = challenge.get('algorithm').lower()
        qop = challenge.get('qop')

        expected = digest.calcResponse(
            digest.calcHA1(algo,
                           "username",
                           "test realm",
                           "password",
                           nonce,
                           cnonce),
            algo, nonce, ncount, cnonce, qop, "GET", "/write/", None
            )
        return expected

    def test_getChallenge(self):
        """
        Test that all the required fields exist in the challenge,
        and that the information matches what we put into our
        DigestCredentialFactory
        """

        challenge = self.credentialFactory.getChallenge(clientAddress)
        self.assertEquals(challenge['qop'], 'auth')
        self.assertEquals(challenge['realm'], 'test realm')
        self.assertEquals(challenge['algorithm'], 'md5')
        self.assertTrue(challenge.has_key("nonce"))
        self.assertTrue(challenge.has_key("opaque"))

    def test_response(self):
        """
        Test that we can decode a valid response to our challenge
        """

        challenge = self.credentialFactory.getChallenge(clientAddress)

        clientResponse = authRequest1 % (
            challenge['nonce'],
            self.getDigestResponse(challenge, "00000001"),
            challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse, _trivial_GET)
        self.failUnless(creds.checkPassword('password'))

    def test_multiResponse(self):
        """
        Test that multiple responses to to a single challenge are handled
        successfully.
        """

        challenge = self.credentialFactory.getChallenge(clientAddress)

        clientResponse = authRequest1 % (
            challenge['nonce'],
            self.getDigestResponse(challenge, "00000001"),
            challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse, _trivial_GET)
        self.failUnless(creds.checkPassword('password'))

        clientResponse = authRequest2 % (
            challenge['nonce'],
            self.getDigestResponse(challenge, "00000002"),
            challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse, _trivial_GET)
        self.failUnless(creds.checkPassword('password'))

    def test_failsWithDifferentMethod(self):
        """
        Test that the response fails if made for a different request method
        than it is being issued for.
        """

        challenge = self.credentialFactory.getChallenge(clientAddress)

        clientResponse = authRequest1 % (
            challenge['nonce'],
            self.getDigestResponse(challenge, "00000001"),
            challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse,
                                              SimpleRequest(None, 'POST', '/'))
        self.failIf(creds.checkPassword('password'))

    def test_noUsername(self):
        """
        Test that login fails when our response does not contain a username,
        or the username field is empty.
        """

        # Check for no username
        e = self.assertRaises(error.LoginFailed,
                              self.credentialFactory.decode,
                              namelessAuthRequest,
                              _trivial_GET)
        self.assertEquals(str(e), "Invalid response, no username given.")

        # Check for an empty username
        e = self.assertRaises(error.LoginFailed,
                              self.credentialFactory.decode,
                              namelessAuthRequest + ',username=""',
                              _trivial_GET)
        self.assertEquals(str(e), "Invalid response, no username given.")

    def test_noNonce(self):
        """
        Test that login fails when our response does not contain a nonce
        """

        e = self.assertRaises(error.LoginFailed,
                              self.credentialFactory.decode,
                              'realm="Test",username="Foo",opaque="bar"',
                              _trivial_GET)
        self.assertEquals(str(e), "Invalid response, no nonce given.")

    def test_noOpaque(self):
        """
        Test that login fails when our response does not contain a nonce
        """

        e = self.assertRaises(error.LoginFailed,
                              self.credentialFactory.decode,
                              'realm="Test",username="Foo"',
                              _trivial_GET)
        self.assertEquals(str(e), "Invalid response, no opaque given.")

    def test_checkHash(self):
        """
        Check that given a hash of the form 'username:realm:password'
        we can verify the digest challenge
        """

        challenge = self.credentialFactory.getChallenge(clientAddress)

        clientResponse = authRequest1 % (
            challenge['nonce'],
            self.getDigestResponse(challenge, "00000001"),
            challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse, _trivial_GET)

        self.failUnless(creds.checkHash(
                md5('username:test realm:password').hexdigest()))

        self.failIf(creds.checkHash(
                md5('username:test realm:bogus').hexdigest()))

    def test_invalidOpaque(self):
        """
        Test that login fails when the opaque does not contain all the required
        parts.
        """

        credentialFactory = FakeDigestCredentialFactory('md5', 'test realm')

        challenge = credentialFactory.getChallenge(clientAddress)

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            'badOpaque',
            challenge['nonce'],
            clientAddress.host)

        badOpaque = ('foo-%s' % (
                'nonce,clientip'.encode('base64').strip('\n'),))

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badOpaque,
            challenge['nonce'],
            clientAddress.host)

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            '',
            challenge['nonce'],
            clientAddress.host)

    def test_incompatibleNonce(self):
        """
        Test that login fails when the given nonce from the response, does not
        match the nonce encoded in the opaque.
        """

        credentialFactory = FakeDigestCredentialFactory('md5', 'test realm')

        challenge = credentialFactory.getChallenge(clientAddress)

        badNonceOpaque = credentialFactory.generateOpaque(
            '1234567890',
            clientAddress.host)

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badNonceOpaque,
            challenge['nonce'],
            clientAddress.host)

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badNonceOpaque,
            '',
            clientAddress.host)

    def test_incompatibleClientIp(self):
        """
        Test that the login fails when the request comes from a client ip
        other than what is encoded in the opaque.
        """

        credentialFactory = FakeDigestCredentialFactory('md5', 'test realm')

        challenge = credentialFactory.getChallenge(clientAddress)

        badNonceOpaque = credentialFactory.generateOpaque(
            challenge['nonce'],
            '10.0.0.1')

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badNonceOpaque,
            challenge['nonce'],
            clientAddress.host)

    def test_oldNonce(self):
        """
        Test that the login fails when the given opaque is older than
        DigestCredentialFactory.CHALLENGE_LIFETIME_SECS
        """

        credentialFactory = FakeDigestCredentialFactory('md5', 'test realm')

        challenge = credentialFactory.getChallenge(clientAddress)

        key = '%s,%s,%s' % (challenge['nonce'],
                            clientAddress.host,
                            '-137876876')
        digest = md5(key + credentialFactory.privateKey).hexdigest()
        ekey = key.encode('base64')

        oldNonceOpaque = '%s-%s' % (digest, ekey.strip('\n'))

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            oldNonceOpaque,
            challenge['nonce'],
            clientAddress.host)

    def test_mismatchedOpaqueChecksum(self):
        """
        Test that login fails when the opaque checksum fails verification
        """

        credentialFactory = FakeDigestCredentialFactory('md5', 'test realm')

        challenge = credentialFactory.getChallenge(clientAddress)


        key = '%s,%s,%s' % (challenge['nonce'],
                            clientAddress.host,
                            '0')

        digest = md5(key + 'this is not the right pkey').hexdigest()

        badChecksum = '%s-%s' % (digest,
                                 key.encode('base64').strip('\n'))

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badChecksum,
            challenge['nonce'],
            clientAddress.host)

    def test_incompatibleCalcHA1Options(self):
        """
        Test that the appropriate error is raised when any of the
        pszUsername, pszRealm, or pszPassword arguments are specified with
        the preHA1 keyword argument.
        """

        arguments = (
            ("user", "realm", "password", "preHA1"),
            (None, "realm", None, "preHA1"),
            (None, None, "password", "preHA1"),
            )

        for pszUsername, pszRealm, pszPassword, preHA1 in arguments:
            self.assertRaises(
                TypeError,
                digest.calcHA1,
                "md5",
                pszUsername,
                pszRealm,
                pszPassword,
                "nonce",
                "cnonce",
                preHA1=preHA1
                )


    def test_noNewlineOpaque(self):
        """
        L{digest.DigestCredentialFactory._generateOpaque} returns a value
        without newlines, regardless of the length of the nonce.
        """
        opaque = self.credentialFactory.generateOpaque(
            "long nonce " * 10, None)
        self.assertNotIn('\n', opaque)



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
            if avatarId == checkers.ANONYMOUS:
                return IHTTPUser, TestHTTPUser('anonymous')

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


class NonAnonymousResource(test_server.BaseTestResource):
    """
    A resource that forces authentication by raising an
    HTTPError with an UNAUTHORIZED code if the request is
    an anonymous one.
    """
    addSlash = True

    sendOwnHeaders = False

    def render(self, req):
        if req.avatar.username == 'anonymous':
            if not self.sendOwnHeaders:
                raise http.HTTPError(responsecode.UNAUTHORIZED)
            else:
                return http.Response(
                    responsecode.UNAUTHORIZED,
                    {'www-authenticate': [('basic', {'realm': 'foo'})]})
        else:
            return super(NonAnonymousResource, self).render(req)


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

    def test_authenticatedRequest(self):
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

    def test_allowedMethods(self):
        """
        Test that unknown methods result in a 401 instead of a 405 when
        authentication hasn't been completed.
        """

        self.method = 'PROPFIND'

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))
        d = self.assertResponse(
            (root, 'http://localhost/'),
            (401,
             {'WWW-Authenticate': [('basic',
                                    {'realm': "test realm"})]},
             None))

        self.method = 'GET'

        return d

    def test_unauthorizedResponse(self):
        """
        Test that a request with no credentials results in a
        valid Unauthorized response.
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        def makeDeepRequest(res):
            return self.assertResponse(
                (root,
                 'http://localhost/foo/bar/baz/bax'),
                (401,
                 {'WWW-Authenticate': [('basic',
                                        {'realm': "test realm"})]},
                 None))

        d = self.assertResponse(
            (root, 'http://localhost/'),
            (401,
             {'WWW-Authenticate': [('basic',
                                    {'realm': "test realm"})]},
             None))

        return d.addCallback(makeDeepRequest)

    def test_badCredentials(self):
        """
        Test that a request with bad credentials results in a valid
        Unauthorized response
        """
        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        credentials = base64.encodestring('bad:credentials')

        d = self.assertResponse(
            (root, 'http://localhost/',
             {'authorization': [('basic', credentials)]}),
            (401,
             {'WWW-Authenticate': [('basic',
                                    {'realm': "test realm"})]},
             None))

        return d

    def test_successfulLogin(self):
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

    def test_wrongScheme(self):
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

    def test_multipleWWWAuthenticateSchemes(self):
        """
        Test that our unauthorized response can contain challenges for
        multiple authentication schemes.
        """
        root = wrapper.HTTPAuthResource(
            self.protectedResource,
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

    def test_authorizationAgainstMultipleSchemes(self):
        """
        Test that we can successfully authenticate when presented
        with multiple WWW-Authenticate headers
        """

        root = wrapper.HTTPAuthResource(
            self.protectedResource,
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
                                     {'authorization': authRequest1}),
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

    def test_wrappedResourceGetsFullSegments(self):
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

    def test_invalidCredentials(self):
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

    def test_anonymousAuthentication(self):
        """
        If our portal has a credentials checker for IAnonymous credentials
        authentication succeeds if no Authorization header is present
        """

        self.portal.registerChecker(checkers.AllowAnonymousAccess())

        self.protectedResource.responseText = "Anonymous access allowed"

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces=(IHTTPUser,))

        def _checkRequest(ign):
            self.assertEquals(
                self.protectedResource.request.avatar.username,
                'anonymous')

        d = self.assertResponse((root, 'http://localhost/',
                                 {}),
                                (200,
                                 {},
                                 "Anonymous access allowed"))
        d.addCallback(_checkRequest)

        return d

    def test_forceAuthentication(self):
        """
        Test that if an HTTPError with an Unauthorized status code is raised
        from within our protected resource, we add the WWW-Authenticate 
        headers if they do not already exist.
        """
        self.portal.registerChecker(checkers.AllowAnonymousAccess())

        nonAnonResource = NonAnonymousResource()
        nonAnonResource.responseText = "We don't like anonymous users"

        root = wrapper.HTTPAuthResource(nonAnonResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces = (IHTTPUser,))

        def _tryAuthenticate(result):
            credentials = base64.encodestring('username:password')

            d2 = self.assertResponse(
                (root, 'http://localhost/',
                 {'authorization': ('basic', credentials)}),
                (200,
                 {},
                 "We don't like anonymous users"))

            return d2

        d = self.assertResponse(
            (root, 'http://localhost/',
             {}),
            (401,
             {'WWW-Authenticate': [('basic',
                                    {'realm': "test realm"})]},
             None))

        d.addCallback(_tryAuthenticate)

        return d

    def test_responseFilterDoesntClobberHeaders(self):
        """
        Test that if an UNAUTHORIZED response is returned and
        already has 'WWW-Authenticate' headers we don't add them.
        """
        self.portal.registerChecker(checkers.AllowAnonymousAccess())

        nonAnonResource = NonAnonymousResource()
        nonAnonResource.responseText = "We don't like anonymous users"
        nonAnonResource.sendOwnHeaders = True

        root = wrapper.HTTPAuthResource(nonAnonResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces = (IHTTPUser,))

        d = self.assertResponse(
            (root, 'http://localhost/',
             {}),
            (401,
             {'WWW-Authenticate': [('basic',
                                    {'realm': "foo"})]},
             None))

        return d

    def test_renderHTTP(self):
        """
        Test that if the renderHTTP method is ever called we authenticate
        the request and delegate rendering to the wrapper.
        """
        self.protectedResource.responseText = "I hope you can see me."
        self.protectedResource.addSlash = True

        root = wrapper.HTTPAuthResource(self.protectedResource,
                                        [self.credFactory],
                                        self.portal,
                                        interfaces = (IHTTPUser,))

        request = SimpleRequest(None, "GET", "/")
        request.prepath = ['']

        def _gotSecondResponse(response):
            self.assertEquals(response.code, 200)
            self.assertEquals(str(response.stream.read()),
                              "I hope you can see me.")

        def _gotResponse(exception):
            response = exception.response

            self.assertEquals(response.code, 401)
            self.failUnless(response.headers.hasHeader('WWW-Authenticate'))
            self.assertEquals(response.headers.getHeader('WWW-Authenticate'),
                              [('basic', {'realm': "test realm"})])

            credentials = base64.encodestring('username:password')

            request.headers.setHeader('authorization',
                                      ['basic', credentials])

            d = root.renderHTTP(request)
            d.addCallback(_gotSecondResponse)

        d = self.assertFailure(root.renderHTTP(request),
                               http.HTTPError)

        d.addCallback(_gotResponse)

        return d


_trivial_GET = SimpleRequest(None, 'GET', '/')
