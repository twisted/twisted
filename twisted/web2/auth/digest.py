# -*- test-case-name: twisted.web2.test.test_httpauth -*-
# Copyright (c) 2006-2009 Twisted Matrix Laboratories.

"""
Implementation of RFC2617: HTTP Digest Authentication

http://www.faqs.org/rfcs/rfc2617.html
"""
import sys
import time
import random

from twisted.cred import credentials, error
from zope.interface import implements, Interface

from twisted.web2.auth.interfaces import ICredentialFactory
from twisted.python.hashlib import md5, sha1

# The digest math

algorithms = {
    'md5': md5,
    'md5-sess': md5,
    'sha': sha1,
}

# DigestCalcHA1
def calcHA1(
    pszAlg,
    pszUserName,
    pszRealm,
    pszPassword,
    pszNonce,
    pszCNonce,
    preHA1=None
):
    """
    @param pszAlg: The name of the algorithm to use to calculate the digest.
        Currently supported are md5 md5-sess and sha.

    @param pszUserName: The username
    @param pszRealm: The realm
    @param pszPassword: The password
    @param pszNonce: The nonce
    @param pszCNonce: The cnonce

    @param preHA1: If available this is a str containing a previously
       calculated HA1 as a hex string. If this is given then the values for
       pszUserName, pszRealm, and pszPassword are ignored.
    """

    if (preHA1 and (pszUserName or pszRealm or pszPassword)):
        raise TypeError(("preHA1 is incompatible with the pszUserName, "
                         "pszRealm, and pszPassword arguments"))

    if preHA1 is None:
        # We need to calculate the HA1 from the username:realm:password
        m = algorithms[pszAlg]()
        m.update(pszUserName)
        m.update(":")
        m.update(pszRealm)
        m.update(":")
        m.update(pszPassword)
        HA1 = m.digest()
    else:
        # We were given a username:realm:password
        HA1 = preHA1.decode('hex')

    if pszAlg == "md5-sess":
        m = algorithms[pszAlg]()
        m.update(HA1)
        m.update(":")
        m.update(pszNonce)
        m.update(":")
        m.update(pszCNonce)
        HA1 = m.digest()

    return HA1.encode('hex')

# DigestCalcResponse
def calcResponse(
    HA1,
    algo,
    pszNonce,
    pszNonceCount,
    pszCNonce,
    pszQop,
    pszMethod,
    pszDigestUri,
    pszHEntity,
):
    m = algorithms[algo]()
    m.update(pszMethod)
    m.update(":")
    m.update(pszDigestUri)
    if pszQop == "auth-int":
        m.update(":")
        m.update(pszHEntity)
    HA2 = m.digest().encode('hex')

    m = algorithms[algo]()
    m.update(HA1)
    m.update(":")
    m.update(pszNonce)
    m.update(":")
    if pszNonceCount and pszCNonce: # pszQop:
        m.update(pszNonceCount)
        m.update(":")
        m.update(pszCNonce)
        m.update(":")
        m.update(pszQop)
        m.update(":")
    m.update(HA2)
    respHash = m.digest().encode('hex')
    return respHash


class IUsernameDigestHash(Interface):
    """
    This credential is used when a CredentialChecker has access to the hash
    of the username:realm:password as in an Apache .htdigest file.
    """
    def checkHash(self, digestHash):
        """
        @param digestHash: The hashed username:realm:password to check against.

        @return: a deferred which becomes, or a boolean indicating if the
            hash matches.
        """


class DigestedCredentials:
    """Yet Another Simple HTTP Digest authentication scheme"""

    implements(credentials.IUsernameHashedPassword,
               IUsernameDigestHash)

    def __init__(self, username, method, realm, fields):
        self.username = username
        self.method = method
        self.realm = realm
        self.fields = fields

    def checkPassword(self, password):
        response = self.fields.get('response')
        uri = self.fields.get('uri')
        nonce = self.fields.get('nonce')
        cnonce = self.fields.get('cnonce')
        nc = self.fields.get('nc')
        algo = self.fields.get('algorithm', 'md5').lower()
        qop = self.fields.get('qop', 'auth')

        expected = calcResponse(
            calcHA1(algo, self.username, self.realm, password, nonce, cnonce),
            algo, nonce, nc, cnonce, qop, self.method, uri, None
        )

        return expected == response

    def checkHash(self, digestHash):
        response = self.fields.get('response')
        uri = self.fields.get('uri')
        nonce = self.fields.get('nonce')
        cnonce = self.fields.get('cnonce')
        nc = self.fields.get('nc')
        algo = self.fields.get('algorithm', 'md5').lower()
        qop = self.fields.get('qop', 'auth')

        expected = calcResponse(
            calcHA1(algo, None, None, None, nonce, cnonce, preHA1=digestHash),
            algo, nonce, nc, cnonce, qop, self.method, uri, None
        )

        return expected == response


class DigestCredentialFactory(object):
    """
    Support for RFC2617 HTTP Digest Authentication

    @cvar CHALLENGE_LIFETIME_SECS: The number of seconds for which an
        opaque should be valid.

    @ivar privateKey: A random string used for generating the secure opaque.
    """

    implements(ICredentialFactory)

    CHALLENGE_LIFETIME_SECS = 15 * 60    # 15 minutes

    scheme = "digest"

    def __init__(self, algorithm, realm):
        """
        @type algorithm: C{str}
        @param algorithm: case insensitive string that specifies
            the hash algorithm used, should be either, md5, md5-sess
            or sha

        @type realm: C{str}
        @param realm: case sensitive string that specifies the realm
            portion of the challenge
        """
        self.algorithm = algorithm
        self.realm = realm

        c = tuple([random.randrange(sys.maxint) for _ in range(3)])

        self.privateKey = '%d%d%d' % c

    def generateNonce(self):
        c = tuple([random.randrange(sys.maxint) for _ in range(3)])
        c = '%d%d%d' % c
        return c

    def _getTime(self):
        """
        Parameterize the time based seed used in generateOpaque
        so we can deterministically unittest it's behavior.
        """
        return time.time()

    def generateOpaque(self, nonce, clientip):
        """
        Generate an opaque to be returned to the client.
        This should be a unique string that can be returned to us and verified.
        """

        # Now, what we do is encode the nonce, client ip and a timestamp
        # in the opaque value with a suitable digest
        key = "%s,%s,%s" % (nonce, clientip, str(int(self._getTime())))
        digest = md5(key + self.privateKey).hexdigest()
        ekey = key.encode('base64')
        return "%s-%s" % (digest, ekey.replace('\n', ''))

    def verifyOpaque(self, opaque, nonce, clientip):
        """
        Given the opaque and nonce from the request, as well as the clientip
        that made the request, verify that the opaque was generated by us.
        And that it's not too old.

        @param opaque: The opaque value from the Digest response
        @param nonce: The nonce value from the Digest response
        @param clientip: The remote IP address of the client making the request

        @return: C{True} if the opaque was successfully verified.

        @raise error.LoginFailed: if C{opaque} could not be parsed or
            contained the wrong values.
        """

        # First split the digest from the key
        opaqueParts = opaque.split('-')
        if len(opaqueParts) != 2:
            raise error.LoginFailed('Invalid response, invalid opaque value')

        # Verify the key
        key = opaqueParts[1].decode('base64')
        keyParts = key.split(',')

        if len(keyParts) != 3:
            raise error.LoginFailed('Invalid response, invalid opaque value')

        if keyParts[0] != nonce:
            raise error.LoginFailed(
                'Invalid response, incompatible opaque/nonce values')

        if keyParts[1] != clientip:
            raise error.LoginFailed(
                'Invalid response, incompatible opaque/client values')

        if (int(self._getTime()) - int(keyParts[2]) >
            DigestCredentialFactory.CHALLENGE_LIFETIME_SECS):

            raise error.LoginFailed(
                'Invalid response, incompatible opaque/nonce too old')

        # Verify the digest
        digest = md5(key + self.privateKey).hexdigest()
        if digest != opaqueParts[0]:
            raise error.LoginFailed('Invalid response, invalid opaque value')

        return True

    def getChallenge(self, peer):
        """
        Generate the challenge for use in the WWW-Authenticate header

        @param peer: The L{IAddress} of the requesting client.

        @return: The C{dict} that can be used to generate a WWW-Authenticate
            header.
        """

        c = self.generateNonce()
        o = self.generateOpaque(c, peer.host)

        return {'nonce': c,
                'opaque': o,
                'qop': 'auth',
                'algorithm': self.algorithm,
                'realm': self.realm}

    def decode(self, response, request):
        """
        Decode the given response and attempt to generate a
        L{DigestedCredentials} from it.

        @type response: C{str}
        @param response: A string of comma seperated key=value pairs

        @type request: L{twisted.web2.server.Request}
        @param request: the request being processed

        @return: L{DigestedCredentials}

        @raise: L{error.LoginFailed} if the response does not contain a
            username, a nonce, an opaque, or if the opaque is invalid.
        """
        def unq(s):
            if s[0] == s[-1] == '"':
                return s[1:-1]
            return s
        response = ' '.join(response.splitlines())
        parts = response.split(',')

        auth = {}

        for (k, v) in [p.split('=', 1) for p in parts]:
            auth[k.strip()] = unq(v.strip())

        username = auth.get('username')
        if not username:
            raise error.LoginFailed('Invalid response, no username given.')

        if 'opaque' not in auth:
            raise error.LoginFailed('Invalid response, no opaque given.')

        if 'nonce' not in auth:
            raise error.LoginFailed('Invalid response, no nonce given.')

        # Now verify the nonce/opaque values for this client
        if self.verifyOpaque(auth.get('opaque'),
                             auth.get('nonce'),
                             request.remoteAddr.host):

            return DigestedCredentials(username,
                                       request.method,
                                       self.realm,
                                       auth)
