# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web._auth}.
"""

import md5, sha

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.cred import error, portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import IUsernamePassword
from twisted.internet.address import IPv4Address
from twisted.web.iweb import ICredentialFactory, IUsernameDigestHash
from twisted.web.resource import IResource, Resource
from twisted.web._auth import basic, digest
from twisted.web._auth.wrapper import HTTPAuthSessionWrapper, UnauthorizedResource
from twisted.web._auth.basic import BasicCredentialFactory
from twisted.web._auth.digest import calcHA1, calcHA2, calcResponse
from twisted.web.server import NOT_DONE_YET
from twisted.web.static import Data

from twisted.web.test.test_web import DummyRequest


def b64encode(s):
    return s.encode('base64').strip()


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



class BasicAuthTestsMixin:
    """
    L{TestCase} mixin class which defines a number of tests for
    L{basic.BasicCredentialFactory}.  Because this mixin defines C{setUp}, it
    must be inherited before L{TestCase}.
    """
    def setUp(self):
        self.request = self.makeRequest()
        self.realm = 'foo'
        self.username = 'dreid'
        self.password = 'S3CuR1Ty'
        self.credentialFactory = basic.BasicCredentialFactory(self.realm)


    def makeRequest(self, method='GET', clientAddress=None):
        """
        Create a request object to be passed to
        L{basic.BasicCredentialFactory.decode} along with a response value.
        Override this in a subclass.
        """
        raise NotImplementedError("%r did not implement makeRequest" % (
                self.__class__,))


    def test_interface(self):
        """
        L{BasicCredentialFactory} implements L{ICredentialFactory}.
        """
        self.assertTrue(
            verifyObject(ICredentialFactory, self.credentialFactory))


    def test_usernamePassword(self):
        """
        L{basic.BasicCredentialFactory.decode} turns a base64-encoded response
        into a L{UsernamePassword} object with a password which reflects the
        one which was encoded in the response.
        """
        response = b64encode('%s:%s' % (self.username, self.password))

        creds = self.credentialFactory.decode(response, self.request)
        self.assertTrue(IUsernamePassword.providedBy(creds))
        self.assertTrue(creds.checkPassword(self.password))
        self.assertFalse(creds.checkPassword(self.password + 'wrong'))


    def test_incorrectPadding(self):
        """
        L{basic.BasicCredentialFactory.decode} decodes a base64-encoded
        response with incorrect padding.
        """
        response = b64encode('%s:%s' % (self.username, self.password))
        response = response.strip('=')

        creds = self.credentialFactory.decode(response, self.request)
        self.assertTrue(verifyObject(IUsernamePassword, creds))
        self.assertTrue(creds.checkPassword(self.password))


    def test_invalidEncoding(self):
        """
        L{basic.BasicCredentialFactory.decode} raises L{LoginFailed} if passed
        a response which is not base64-encoded.
        """
        response = 'x' # one byte cannot be valid base64 text
        self.assertRaises(
            error.LoginFailed,
            self.credentialFactory.decode, response, self.makeRequest())


    def test_invalidCredentials(self):
        """
        L{basic.BasicCredentialFactory.decode} raises L{LoginFailed} when
        passed a response which is not valid base64-encoded text.
        """
        response = b64encode('123abc+/')
        self.assertRaises(
            error.LoginFailed,
            self.credentialFactory.decode,
            response, self.makeRequest())


class RequestMixin:
    def makeRequest(self, method='GET', clientAddress=None):
        """
        Create a L{DummyRequest} (change me to create a
        L{twisted.web.http.Request} instead).
        """
        request = DummyRequest('/')
        request.method = method
        request.client = clientAddress
        return request



class BasicAuthTestCase(RequestMixin, BasicAuthTestsMixin, unittest.TestCase):
    """
    Basic authentication tests which use L{twisted.web.http.Request}.
    """



class DigestAuthTestsMixin:
    """
    L{TestCase} mixin class which defines a number of tests for
    L{digest.DigestCredentialFactory}.  Because this mixin defines C{setUp}, it
    must be inherited before L{TestCase}.
    """
    def setUp(self):
        """
        Create a DigestCredentialFactory for testing
        """
        self.username = "foobar"
        self.password = "bazquux"
        self.realm = "test realm"
        self.algorithm = "md5"
        self.cnonce = "29fc54aa1641c6fa0e151419361c8f23"
        self.qop = "auth"
        self.uri = "/write/"
        self.clientAddress = IPv4Address('TCP', '10.2.3.4', 43125)
        self.request = self.makeRequest('GET', self.clientAddress)
        self.credentialFactory = digest.DigestCredentialFactory(
            self.algorithm, self.realm)


    def test_MD5HashA1(self, _algorithm='md5', _hash=md5.md5):
        """
        L{calcHA1} accepts the C{'md5'} algorithm and returns an MD5 hash of
        its parameters, excluding the nonce and cnonce.
        """
        nonce = 'abc123xyz'
        hashA1 = calcHA1(_algorithm, self.username, self.realm, self.password,
                         nonce, self.cnonce)
        a1 = '%s:%s:%s' % (self.username, self.realm, self.password)
        expected = _hash(a1).hexdigest()
        self.assertEqual(hashA1, expected)


    def test_MD5SessionHashA1(self):
        """
        L{calcHA1} accepts the C{'md5-sess'} algorithm and returns an MD5 hash
        of its parameters, including the nonce and cnonce.
        """
        nonce = 'xyz321abc'
        hashA1 = calcHA1('md5-sess', self.username, self.realm, self.password,
                         nonce, self.cnonce)
        a1 = '%s:%s:%s' % (self.username, self.realm, self.password)
        ha1 = md5.md5(a1).digest()
        a1 = '%s:%s:%s' % (ha1, nonce, self.cnonce)
        expected = md5.md5(a1).hexdigest()
        self.assertEqual(hashA1, expected)


    def test_SHAHashA1(self):
        """
        L{calcHA1} accepts the C{'sha'} algorithm and returns a SHA hash of its
        parameters, excluding the nonce and cnonce.
        """
        self.test_MD5HashA1('sha', sha.sha)


    def test_MD5HashA2Auth(self, _algorithm='md5', _hash=md5.md5):
        """
        L{calcHA2} accepts the C{'md5'} algorithm and returns an MD5 hash of
        its arguments, excluding the entity hash for QOP other than
        C{'auth-int'}.
        """
        method = 'GET'
        hashA2 = calcHA2(_algorithm, method, self.uri, 'auth', None)
        a2 = '%s:%s' % (method, self.uri)
        expected = _hash(a2).hexdigest()
        self.assertEqual(hashA2, expected)


    def test_MD5HashA2AuthInt(self, _algorithm='md5', _hash=md5.md5):
        """
        L{calcHA2} accepts the C{'md5'} algorithm and returns an MD5 hash of
        its arguments, including the entity hash for QOP of C{'auth-int'}.
        """
        method = 'GET'
        hentity = 'foobarbaz'
        hashA2 = calcHA2(_algorithm, method, self.uri, 'auth-int', hentity)
        a2 = '%s:%s:%s' % (method, self.uri, hentity)
        expected = _hash(a2).hexdigest()
        self.assertEqual(hashA2, expected)


    def test_MD5SessHashA2Auth(self):
        """
        L{calcHA2} accepts the C{'md5-sess'} algorithm and QOP of C{'auth'} and
        returns the same value as it does for the C{'md5'} algorithm.
        """
        self.test_MD5HashA2Auth('md5-sess')


    def test_MD5SessHashA2AuthInt(self):
        """
        L{calcHA2} accepts the C{'md5-sess'} algorithm and QOP of C{'auth-int'}
        and returns the same value as it does for the C{'md5'} algorithm.
        """
        self.test_MD5HashA2AuthInt('md5-sess')


    def test_SHAHashA2Auth(self):
        """
        L{calcHA2} accepts the C{'sha'} algorithm and returns a SHA hash of
        its arguments, excluding the entity hash for QOP other than
        C{'auth-int'}.
        """
        self.test_MD5HashA2Auth('sha', sha.sha)


    def test_SHAHashA2AuthInt(self):
        """
        L{calcHA2} accepts the C{'sha'} algorithm and returns a SHA hash of
        its arguments, including the entity hash for QOP of C{'auth-int'}.
        """
        self.test_MD5HashA2AuthInt('sha', sha.sha)


    def test_MD5HashResponse(self, _algorithm='md5', _hash=md5.md5):
        """
        L{calcResponse} accepts the C{'md5'} algorithm and returns an MD5 hash
        of its parameters, excluding the nonce count, client nonce, and QoP
        value if the nonce count and client nonce are C{None}
        """
        hashA1 = 'abc123'
        hashA2 = '789xyz'
        nonce = 'lmnopq'

        response = '%s:%s:%s' % (hashA1, nonce, hashA2)
        expected = _hash(response).hexdigest()

        digest = calcResponse(hashA1, hashA2, _algorithm, nonce, None, None, None)
        self.assertEqual(expected, digest)


    def test_MD5SessionHashResponse(self):
        """
        L{calcResponse} accepts the C{'md5-sess'} algorithm and returns an MD5
        hash of its parameters, excluding the nonce count, client nonce, and
        QoP value if the nonce count and client nonce are C{None}
        """
        self.test_MD5HashResponse('md5-sess')


    def test_SHAHashResponse(self):
        """
        L{calcResponse} accepts the C{'sha'} algorithm and returns a SHA hash
        of its parameters, excluding the nonce count, client nonce, and QoP
        value if the nonce count and client nonce are C{None}
        """
        self.test_MD5HashResponse('sha', sha.sha)


    def test_MD5HashResponseExtra(self, _algorithm='md5', _hash=md5.md5):
        """
        L{calcResponse} accepts the C{'md5'} algorithm and returns an MD5 hash
        of its parameters, including the nonce count, client nonce, and QoP
        value if they are specified.
        """
        hashA1 = 'abc123'
        hashA2 = '789xyz'
        nonce = 'lmnopq'
        nonceCount = '00000004'
        clientNonce = 'abcxyz123'
        qop = 'auth'

        response = '%s:%s:%s:%s:%s:%s' % (
            hashA1, nonce, nonceCount, clientNonce, qop, hashA2)
        expected = _hash(response).hexdigest()

        digest = calcResponse(
            hashA1, hashA2, _algorithm, nonce, nonceCount, clientNonce, qop)
        self.assertEqual(expected, digest)


    def test_MD5SessionHashResponseExtra(self):
        """
        L{calcResponse} accepts the C{'md5-sess'} algorithm and returns an MD5
        hash of its parameters, including the nonce count, client nonce, and
        QoP value if they are specified.
        """
        self.test_MD5HashResponseExtra('md5-sess')


    def test_SHAHashResponseExtra(self):
        """
        L{calcResponse} accepts the C{'sha'} algorithm and returns a SHA hash
        of its parameters, including the nonce count, client nonce, and QoP
        value if they are specified.
        """
        self.test_MD5HashResponseExtra('sha', sha.sha)


    def makeRequest(self, method='GET', clientAddress=None):
        """
        Create a request object to be passed to
        L{basic.DigestCredentialFactory.decode} along with a response value.
        Override this in a subclass.
        """
        raise NotImplementedError("%r did not implement makeRequest" % (
                self.__class__,))


    def formatResponse(self, quotes=True, **kw):
        """
        Format all given keyword arguments and their values suitably for use as
        the value of an HTTP header.

        @types quotes: C{bool}
        @param quotes: A flag indicating whether to quote the values of each
            field in the response.

        @param **kw: Keywords and C{str} values which will be treated as field
            name/value pairs to include in the result.

        @rtype: C{str}
        @return: The given fields formatted for use as an HTTP header value.
        """
        if 'username' not in kw:
            kw['username'] = self.username
        if 'realm' not in kw:
            kw['realm'] = self.realm
        if 'algorithm' not in kw:
            kw['algorithm'] = self.algorithm
        if 'qop' not in kw:
            kw['qop'] = self.qop
        if 'cnonce' not in kw:
            kw['cnonce'] = self.cnonce
        if 'uri' not in kw:
            kw['uri'] = self.uri
        if quotes:
            quote = '"'
        else:
            quote = ''
        return ', '.join([
                '%s=%s%s%s' % (k, quote, v, quote)
                for (k, v)
                in kw.iteritems()
                if v is not None])


    def getDigestResponse(self, challenge, ncount):
        """
        Calculate the response for the given challenge
        """
        nonce = challenge.get('nonce')
        algo = challenge.get('algorithm').lower()
        qop = challenge.get('qop')

        ha1 = calcHA1(
            algo, self.username, self.realm, self.password, nonce, self.cnonce)
        ha2 = calcHA2(algo, "GET", self.uri, qop, None)
        expected = calcResponse(ha1, ha2, algo, nonce, ncount, self.cnonce, qop)
        return expected


    def test_interface(self):
        """
        L{DigestCredentialFactory} implements L{ICredentialFactory}.
        """
        self.assertTrue(
            verifyObject(ICredentialFactory, self.credentialFactory))


    def test_getChallenge(self):
        """
        The challenge issued by L{DigestCredentialFactory.getChallenge} must
        include C{'qop'}, C{'realm'}, C{'algorithm'}, C{'nonce'}, and
        C{'opaque'} keys.  The values for the C{'realm'} and C{'algorithm'}
        keys must match the values supplied to the factory's initializer. 
        None of the values may have newlines in them.
        """
        challenge = self.credentialFactory.getChallenge(self.request)
        self.assertEquals(challenge['qop'], 'auth')
        self.assertEquals(challenge['realm'], 'test realm')
        self.assertEquals(challenge['algorithm'], 'md5')
        self.assertIn('nonce', challenge)
        self.assertIn('opaque', challenge)
        for v in challenge.values():
            self.assertNotIn('\n', v)


    def test_getChallengeWithoutClientIP(self):
        """
        L{DigestCredentialFactory.getChallenge} can issue a challenge even if
        the L{Request} it is passed returns C{None} from C{getClientIP}.
        """
        request = self.makeRequest('GET', None)
        challenge = self.credentialFactory.getChallenge(request)
        self.assertEqual(challenge['qop'], 'auth')
        self.assertEqual(challenge['realm'], 'test realm')
        self.assertEqual(challenge['algorithm'], 'md5')
        self.assertIn('nonce', challenge)
        self.assertIn('opaque', challenge)


    def test_response(self, quotes=True):
        """
        L{DigestCredentialFactory.decode} accepts a digest challenge response
        and parses it into an L{IUsernameHashedPassword} provider.
        """
        challenge = self.credentialFactory.getChallenge(self.request)

        nc = "00000001"
        clientResponse = self.formatResponse(
            quotes=quotes,
            nonce=challenge['nonce'],
            response=self.getDigestResponse(challenge, nc),
            nc=nc,
            opaque=challenge['opaque'])
        creds = self.credentialFactory.decode(
            clientResponse, self.request)
        self.assertTrue(creds.checkPassword(self.password))
        self.assertFalse(creds.checkPassword(self.password + 'wrong'))


    def test_responseWithoutQuotes(self):
        """
        L{DigestCredentialFactory.decode} accepts a digest challenge response
        which does not quote the values of its fields and parses it into an
        L{IUsernameHashedPassword} provider in the same way it would a
        response which included quoted field values.
        """
        self.test_response(False)


    def test_caseInsensitiveAlgorithm(self):
        """
        The case of the algorithm value in the response is ignored when
        checking the credentials.
        """
        self.algorithm = 'MD5'
        self.test_response()


    def test_md5DefaultAlgorithm(self):
        """
        The algorithm defaults to MD5 if it is not supplied in the response.
        """
        self.algorithm = None
        self.test_response()


    def test_responseWithoutClientIP(self):
        """
        L{DigestCredentialFactory.decode} accepts a digest challenge response
        even if the L{Request} it is passed returns C{None} from
        C{getClientIP}.
        """
        request = self.makeRequest('GET', None)
        challenge = self.credentialFactory.getChallenge(request)

        nc = "00000001"
        clientResponse = self.formatResponse(
            nonce=challenge['nonce'],
            response=self.getDigestResponse(challenge, nc),
            nc=nc,
            opaque=challenge['opaque'])
        creds = self.credentialFactory.decode(clientResponse, request)
        self.assertTrue(creds.checkPassword(self.password))
        self.assertFalse(creds.checkPassword(self.password + 'wrong'))


    def test_multiResponse(self):
        """
        L{DigestCredentialFactory.decode} handles multiple responses to a
        single challenge.
        """
        challenge = self.credentialFactory.getChallenge(self.request)

        nc = "00000001"
        clientResponse = self.formatResponse(
            nonce=challenge['nonce'],
            response=self.getDigestResponse(challenge, nc),
            nc=nc,
            opaque=challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse, self.request)
        self.assertTrue(creds.checkPassword(self.password))
        self.assertFalse(creds.checkPassword(self.password + 'wrong'))

        nc = "00000002"
        clientResponse = self.formatResponse(
            nonce=challenge['nonce'],
            response=self.getDigestResponse(challenge, nc),
            nc=nc,
            opaque=challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse, self.request)
        self.assertTrue(creds.checkPassword(self.password))
        self.assertFalse(creds.checkPassword(self.password + 'wrong'))


    def test_failsWithDifferentMethod(self):
        """
        L{DigestCredentialFactory.decode} returns an L{IUsernameHashedPassword}
        provider which rejects a correct password for the given user if the
        challenge response request is made using a different HTTP method than
        was used to request the initial challenge.
        """
        challenge = self.credentialFactory.getChallenge(self.request)

        nc = "00000001"
        clientResponse = self.formatResponse(
            nonce=challenge['nonce'],
            response=self.getDigestResponse(challenge, nc),
            nc=nc,
            opaque=challenge['opaque'])

        postRequest = self.makeRequest('POST', self.clientAddress)
        creds = self.credentialFactory.decode(clientResponse, postRequest)
        self.assertFalse(creds.checkPassword(self.password))
        self.assertFalse(creds.checkPassword(self.password + 'wrong'))


    def test_noUsername(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} if the response
        has no username field or if the username field is empty.
        """
        # Check for no username
        e = self.assertRaises(
            error.LoginFailed,
            self.credentialFactory.decode,
            self.formatResponse(username=None),
            self.request)
        self.assertEqual(str(e), "Invalid response, no username given.")

        # Check for an empty username
        e = self.assertRaises(
            error.LoginFailed,
            self.credentialFactory.decode,
            self.formatResponse(username=""),
            self.request)
        self.assertEqual(str(e), "Invalid response, no username given.")


    def test_noNonce(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} if the response
        has no nonce.
        """
        e = self.assertRaises(
            error.LoginFailed,
            self.credentialFactory.decode,
            self.formatResponse(opaque="abc123"),
            self.request)
        self.assertEqual(str(e), "Invalid response, no nonce given.")


    def test_noOpaque(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} if the response
        has no opaque.
        """
        e = self.assertRaises(
            error.LoginFailed,
            self.credentialFactory.decode,
            self.formatResponse(),
            self.request)
        self.assertEqual(str(e), "Invalid response, no opaque given.")


    def test_checkHash(self):
        """
        L{DigestCredentialFactory.decode} returns an L{IUsernameDigestHash}
        provider which can verify a hash of the form 'username:realm:password'.
        """
        challenge = self.credentialFactory.getChallenge(self.request)

        nc = "00000001"
        clientResponse = self.formatResponse(
            nonce=challenge['nonce'],
            response=self.getDigestResponse(challenge, nc),
            nc=nc,
            opaque=challenge['opaque'])

        creds = self.credentialFactory.decode(clientResponse, self.request)
        self.assertTrue(verifyObject(IUsernameDigestHash, creds))

        cleartext = '%s:%s:%s' % (self.username, self.realm, self.password)
        hash = md5.md5(cleartext)
        self.assertTrue(creds.checkHash(hash.hexdigest()))
        hash.update('wrong')
        self.assertFalse(creds.checkHash(hash.hexdigest()))


    def test_invalidOpaque(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} when the opaque
        value does not contain all the required parts.
        """
        credentialFactory = FakeDigestCredentialFactory(self.algorithm, self.realm)
        challenge = credentialFactory.getChallenge(self.request)

        exc = self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            'badOpaque',
            challenge['nonce'],
            self.clientAddress.host)
        self.assertEqual(str(exc), 'Invalid response, invalid opaque value')

        badOpaque = 'foo-' + b64encode('nonce,clientip')

        exc = self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badOpaque,
            challenge['nonce'],
            self.clientAddress.host)
        self.assertEqual(str(exc), 'Invalid response, invalid opaque value')

        exc = self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            '',
            challenge['nonce'],
            self.clientAddress.host)
        self.assertEqual(str(exc), 'Invalid response, invalid opaque value')

        badOpaque = (
            'foo-' + b64encode('%s,%s,foobar' % (
                    challenge['nonce'],
                    self.clientAddress.host)))
        exc = self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badOpaque,
            challenge['nonce'],
            self.clientAddress.host)
        self.assertEqual(
            str(exc), 'Invalid response, invalid opaque/time values')


    def test_incompatibleNonce(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} when the given
        nonce from the response does not match the nonce encoded in the opaque.
        """
        credentialFactory = FakeDigestCredentialFactory(self.algorithm, self.realm)
        challenge = credentialFactory.getChallenge(self.request)

        badNonceOpaque = credentialFactory.generateOpaque(
            '1234567890',
            self.clientAddress.host)

        exc = self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badNonceOpaque,
            challenge['nonce'],
            self.clientAddress.host)
        self.assertEqual(
            str(exc),
            'Invalid response, incompatible opaque/nonce values')

        exc = self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badNonceOpaque,
            '',
            self.clientAddress.host)
        self.assertEqual(
            str(exc),
            'Invalid response, incompatible opaque/nonce values')


    def test_incompatibleClientIP(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} when the
        request comes from a client IP other than what is encoded in the
        opaque.
        """
        credentialFactory = FakeDigestCredentialFactory(self.algorithm, self.realm)
        challenge = credentialFactory.getChallenge(self.request)

        badAddress = '10.0.0.1'
        # Sanity check
        self.assertNotEqual(self.clientAddress.host, badAddress)

        badNonceOpaque = credentialFactory.generateOpaque(
            challenge['nonce'], badAddress)

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badNonceOpaque,
            challenge['nonce'],
            self.clientAddress.host)


    def test_oldNonce(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} when the given
        opaque is older than C{DigestCredentialFactory.CHALLENGE_LIFETIME_SECS}
        """
        credentialFactory = FakeDigestCredentialFactory(self.algorithm, self.realm)
        challenge = credentialFactory.getChallenge(self.request)

        key = '%s,%s,%s' % (challenge['nonce'],
                            self.clientAddress.host,
                            '-137876876')
        digest = md5.md5(key + credentialFactory.privateKey).hexdigest()
        ekey = b64encode(key)

        oldNonceOpaque = '%s-%s' % (digest, ekey.strip('\n'))

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            oldNonceOpaque,
            challenge['nonce'],
            self.clientAddress.host)


    def test_mismatchedOpaqueChecksum(self):
        """
        L{DigestCredentialFactory.decode} raises L{LoginFailed} when the opaque
        checksum fails verification.
        """
        credentialFactory = FakeDigestCredentialFactory(self.algorithm, self.realm)
        challenge = credentialFactory.getChallenge(self.request)

        key = '%s,%s,%s' % (challenge['nonce'],
                            self.clientAddress.host,
                            '0')

        digest = md5.md5(key + 'this is not the right pkey').hexdigest()
        badChecksum = '%s-%s' % (digest, b64encode(key))

        self.assertRaises(
            error.LoginFailed,
            credentialFactory.verifyOpaque,
            badChecksum,
            challenge['nonce'],
            self.clientAddress.host)


    def test_incompatibleCalcHA1Options(self):
        """
        L{calcHA1} raises L{TypeError} when any of the pszUsername, pszRealm,
        or pszPassword arguments are specified with the preHA1 keyword
        argument.
        """
        arguments = (
            ("user", "realm", "password", "preHA1"),
            (None, "realm", None, "preHA1"),
            (None, None, "password", "preHA1"),
            )

        for pszUsername, pszRealm, pszPassword, preHA1 in arguments:
            self.assertRaises(
                TypeError,
                calcHA1,
                "md5",
                pszUsername,
                pszRealm,
                pszPassword,
                "nonce",
                "cnonce",
                preHA1=preHA1)



class DigestAuthTestCase(RequestMixin, DigestAuthTestsMixin, unittest.TestCase):
    """
    Digest authentication tests which use L{twisted.web.http.Request}.
    """


def render(resource, request):
    result = resource.render(request)
    if result is NOT_DONE_YET:
        return
    request.write(result)
    request.finish()


class UnauthorizedResourceTests(unittest.TestCase):
    """
    Tests for L{UnauthorizedResource}.
    """
    def test_getChildWithDefault(self):
        """
        An L{UnauthorizedResource} is every child of itself.
        """
        resource = UnauthorizedResource([])
        self.assertIdentical(
            resource.getChildWithDefault("foo", None), resource)
        self.assertIdentical(
            resource.getChildWithDefault("bar", None), resource)


    def test_render(self):
        """
        L{UnauthorizedResource} renders with a 401 response code and a
        I{WWW-Authenticate} header and puts a simple unauthorized message
        into the response body.
        """
        resource = UnauthorizedResource([
                BasicCredentialFactory('example.com')])
        request = DummyRequest([''])
        render(resource, request)
        self.assertEqual(request.responseCode, 401)
        self.assertEqual(
            request.responseHeaders.getRawHeaders('www-authenticate'),
            ['basic realm="example.com"'])
        self.assertEqual(request.written, ['Unauthorized'])


    def test_renderQuotesRealm(self):
        """
        The realm value included in the I{WWW-Authenticate} header set in
        the response when L{UnauthorizedResounrce} is rendered has quotes
        and backslashes escaped.
        """
        resource = UnauthorizedResource([
                BasicCredentialFactory('example\\"foo')])
        request = DummyRequest([''])
        render(resource, request)
        self.assertEqual(
            request.responseHeaders.getRawHeaders('www-authenticate'),
            ['basic realm="example\\\\\\"foo"'])



class Realm(object):
    """
    A simple L{IRealm} implementation which gives out L{WebAvatar} for any
    avatarId.

    @type loggedIn: C{int}
    @ivar loggedIn: The number of times C{requestAvatar} has been invoked for
        L{IResource}.

    @type loggedOut: C{int}
    @ivar loggedOut: The number of times the logout callback has been invoked.
    """
    implements(portal.IRealm)

    def __init__(self, avatarFactory):
        self.loggedOut = 0
        self.loggedIn = 0
        self.avatarFactory = avatarFactory


    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            self.loggedIn += 1
            return IResource, self.avatarFactory(avatarId), self.logout
        raise NotImplementedError()


    def logout(self):
        self.loggedOut += 1



class HTTPAuthHeaderTests(unittest.TestCase):
    """
    Tests for L{HTTPAuthSessionWrapper}.
    """
    makeRequest = DummyRequest

    def setUp(self):
        """
        Create a realm, portal, and L{HTTPAuthSessionWrapper} to use in the tests.
        """
        self.username = 'foo bar'
        self.password = 'bar baz'
        self.childName = "foo-child"
        self.childContent = "contents of the foo child of the avatar"
        self.checker = InMemoryUsernamePasswordDatabaseDontUse()
        self.checker.addUser(self.username, self.password)
        self.avatar = Resource()
        self.avatar.putChild(
            self.childName, Data(self.childContent, 'text/plain'))
        self.avatars = {self.username: self.avatar}
        self.realm = Realm(self.avatars.get)
        self.portal = portal.Portal(self.realm, [self.checker])
        self.credentialFactories = []
        self.wrapper = HTTPAuthSessionWrapper(
            self.portal, self.credentialFactories)


    def _authorizedBasicLogin(self, request, creds=None):
        if creds is None:
            username, password = self.username, self.password
        else:
            username, password = creds
        authorization = b64encode(username + ':' + password)
        request.headers['authorization'] = 'Basic ' + authorization
        child = self.wrapper.getChildWithDefault(request.postpath[0], request)
        return child


    def test_getChildWithDefault(self):
        """
        L{HTTPAuthSessionWrapper.getChildWithDefault} returns an
        L{UnauthorizedResource} instance when called with a request which does
        not have the required I{Authorization} headers.
        """
        request = self.makeRequest([self.childName])
        child = self.wrapper.getChildWithDefault(self.childName, request)
        self.assertIsInstance(child, UnauthorizedResource)


    def _invalidAuthorizationTest(self, response):
        self.credentialFactories.append(BasicCredentialFactory('example.com'))
        request = self.makeRequest([self.childName])
        request.headers['authorization'] = response
        child = self.wrapper.getChildWithDefault(self.childName, request)
        d = request.notifyFinish()
        def cbFinished(result):
            self.assertEqual(request.responseCode, 401)
        d.addCallback(cbFinished)
        render(child, request)
        return d


    def test_getChildWithDefaultUnauthorizedUser(self):
        """
        If L{HTTPAuthSessionWrapper.getChildWithDefault} is called with a
        request with an I{Authorization} header with a user which does not
        exist, an L{IResource} which renders a 401 response code is returned.
        """
        return self._invalidAuthorizationTest('Basic ' + b64encode('foo:bar'))


    def test_getChildWithDefaultUnauthorizedPassword(self):
        """
        If L{HTTPAuthSessionWrapper.getChildWithDefault} is called with a
        request with an I{Authorization} header with a user which exists and
        the wrong password, an L{IResource} which renders a 401 response code
        is returned.
        """
        return self._invalidAuthorizationTest(
            'Basic ' + b64encode(self.username + ':bar'))


    def test_getChildWithDefaultUnrecognizedScheme(self):
        """
        If L{HTTPAuthSessionWrapper.getChildWithDefault} is called with a
        request with an I{Authorization} header with an unrecognized scheme, an
        L{IResource} which renders a 401 response code is returned.
        """
        return self._invalidAuthorizationTest('Quux foo bar baz')


    def test_getChildWithDefaultAuthorized(self):
        """
        When called with a request with a valid I{Authorization} header,
        L{HTTPAuthSessionWrapper.getChildWithDefault} returns an L{IResource}
        which renders the L{IResource} avatar retrieved from the portal.
        """
        self.credentialFactories.append(BasicCredentialFactory('example.com'))
        request = self.makeRequest([self.childName])
        child = self._authorizedBasicLogin(request)
        d = request.notifyFinish()
        def cbFinished(ignored):
            self.assertEquals(request.written, [self.childContent])
        d.addCallback(cbFinished)
        render(child, request)
        return d


    def test_getChallengeCalledWithRequest(self):
        """
        When L{HTTPAuthSessionWrapper} finds an L{ICredentialFactory} to issue
        a challenge, it calls the C{getChallenge} method with the request as an
        argument.
        """
        class DumbCredentialFactory(object):
            implements(ICredentialFactory)
            scheme = 'dumb'

            def __init__(self):
                self.requests = []

            def getChallenge(self, request):
                self.requests.append(request)
                return {}

        factory = DumbCredentialFactory()
        self.credentialFactories.append(factory)
        request = self.makeRequest([self.childName])
        child = self.wrapper.getChildWithDefault(request.postpath[0], request)
        d = request.notifyFinish()
        def cbFinished(ignored):
            self.assertEqual(factory.requests, [request])
        d.addCallback(cbFinished)
        render(child, request)
        return d


    def test_logout(self):
        """
        The realm's logout callback is invoked after the resource is rendered.
        """
        self.credentialFactories.append(BasicCredentialFactory('example.com'))

        class SlowerResource(Resource):
            def render(self, request):
                return NOT_DONE_YET

        self.avatar.putChild(self.childName, SlowerResource())
        request = self.makeRequest([self.childName])
        child = self._authorizedBasicLogin(request)
        render(child, request)
        self.assertEqual(self.realm.loggedOut, 0)
        request.finish()
        self.assertEqual(self.realm.loggedOut, 1)


    def test_decodeRaises(self):
        """
        L{HTTPAuthSessionWrapper.getChildWithDefault} returns an
        L{UnauthorizedResource} instance when called with a request which has a
        I{Basic Authorization} header which cannot be decoded using base64.
        """
        self.credentialFactories.append(BasicCredentialFactory('example.com'))
        request = self.makeRequest([self.childName])
        request.headers['authorization'] = 'Basic decode should fail'
        child = self.wrapper.getChildWithDefault(self.childName, request)
        self.assertIsInstance(child, UnauthorizedResource)


    def test_selectParseResponse(self):
        """
        L{HTTPAuthSessionWrapper._selectParseHeader} returns a two-tuple giving
        the L{ICredentialFactory} to use to parse the header and a string
        containing the portion of the header which remains to be parsed.
        """
        basicAuthorization = 'Basic abcdef123456'
        self.assertEqual(
            self.wrapper._selectParseHeader(basicAuthorization),
            (None, None))
        factory = BasicCredentialFactory('example.com')
        self.credentialFactories.append(factory)
        self.assertEqual(
            self.wrapper._selectParseHeader(basicAuthorization),
            (factory, 'abcdef123456'))


    def test_unexpectedDecodeError(self):
        """
        Any unexpected exception raised by the credential factory's C{decode}
        method results in a 500 response code and causes the exception to be
        logged.
        """
        class UnexpectedException(Exception):
            pass

        class BadFactory(object):
            scheme = 'bad'

            def getChallenge(self, client):
                return {}

            def decode(self, response, request):
                raise UnexpectedException()

        self.credentialFactories.append(BadFactory())
        request = self.makeRequest([self.childName])
        request.headers['authorization'] = 'Bad abc'
        child = self.wrapper.getChildWithDefault(self.childName, request)
        render(child, request)
        self.assertEqual(request.responseCode, 500)
        self.assertEqual(len(self.flushLoggedErrors(UnexpectedException)), 1)


    def test_unexpectedLoginError(self):
        """
        Any unexpected failure from L{Portal.login} results in a 500 response
        code and causes the failure to be logged.
        """
        class UnexpectedException(Exception):
            pass

        class BrokenChecker(object):
            credentialInterfaces = (IUsernamePassword,)

            def requestAvatarId(self, credentials):
                raise UnexpectedException()

        self.portal.registerChecker(BrokenChecker())
        self.credentialFactories.append(BasicCredentialFactory('example.com'))
        request = self.makeRequest([self.childName])
        child = self._authorizedBasicLogin(request)
        render(child, request)
        self.assertEqual(request.responseCode, 500)
        self.assertEqual(len(self.flushLoggedErrors(UnexpectedException)), 1)
