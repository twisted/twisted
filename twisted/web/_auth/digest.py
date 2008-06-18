# -*- test-case-name: twisted.web.test.test_httpauth -*-
# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of RFC2617: HTTP Digest Authentication

@see: U{http://www.faqs.org/rfcs/rfc2617.html}
"""

import time
import md5, sha

from zope.interface import implements

from twisted.python.randbytes import secureRandom
from twisted.cred import credentials, error
from twisted.web.iweb import ICredentialFactory, IUsernameDigestHash


# The digest math

algorithms = {
    'md5': md5.new,

    # md5-sess is more complicated than just another algorithm.  It requires
    # H(A1) state to be remembered from the first WWW-Authenticate challenge
    # issued and re-used to process any Authorization header in response to
    # that WWW-Authenticate challenge.  It is *not* correct to simply
    # recalculate H(A1) each time an Authorization header is received.  Read
    # RFC 2617, section 3.2.2.2 and do not try to make DigestCredentialFactory
    # support this unless you completely understand it. -exarkun
    'md5-sess': md5.new,

    'sha': sha.new,
}

# DigestCalcHA1
def calcHA1(pszAlg, pszUserName, pszRealm, pszPassword, pszNonce, pszCNonce,
            preHA1=None):
    """
    Compute H(A1) from RFC 2617.

    @param pszAlg: The name of the algorithm to use to calculate the digest.
        Currently supported are md5, md5-sess, and sha.
    @param pszUserName: The username
    @param pszRealm: The realm
    @param pszPassword: The password
    @param pszNonce: The nonce
    @param pszCNonce: The cnonce

    @param preHA1: If available this is a str containing a previously
       calculated H(A1) as a hex string.  If this is given then the values for
       pszUserName, pszRealm, and pszPassword must be C{None} and are ignored.
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


def calcHA2(algo, pszMethod, pszDigestUri, pszQop, pszHEntity):
    """
    Compute H(A2) from RFC 2617.

    @param pszAlg: The name of the algorithm to use to calculate the digest.
        Currently supported are md5, md5-sess, and sha.
    @param pszMethod: The request method.
    @param pszDigestUri: The request URI.
    @param pszQop: The Quality-of-Protection value.
    @param pszHEntity: The hash of the entity body or C{None} if C{pszQop} is
        not C{'auth-int'}.
    @return: The hash of the A2 value for the calculation of the response
        digest.
    """
    m = algorithms[algo]()
    m.update(pszMethod)
    m.update(":")
    m.update(pszDigestUri)
    if pszQop == "auth-int":
        m.update(":")
        m.update(pszHEntity)
    return m.digest().encode('hex')


def calcResponse(HA1, HA2, algo, pszNonce, pszNonceCount, pszCNonce, pszQop):
    """
    Compute the digest for the given parameters.

    @param HA1: The H(A1) value, as computed by L{calcHA1}.
    @param HA2: The H(A2) value, as computed by L{calcHA2}.
    @param pszNonce: The challenge nonce.
    @param pszNonceCount: The (client) nonce count value for this response.
    @param pszCNonce: The client nonce.
    @param pszQop: The Quality-of-Protection value.
    """
    m = algorithms[algo]()
    m.update(HA1)
    m.update(":")
    m.update(pszNonce)
    m.update(":")
    if pszNonceCount and pszCNonce:
        m.update(pszNonceCount)
        m.update(":")
        m.update(pszCNonce)
        m.update(":")
        m.update(pszQop)
        m.update(":")
    m.update(HA2)
    respHash = m.digest().encode('hex')
    return respHash



class DigestedCredentials(object):
    """
    Yet Another Simple HTTP Digest authentication scheme.
    """
    implements(credentials.IUsernameHashedPassword, IUsernameDigestHash)

    def __init__(self, username, method, realm, fields):
        self.username = username
        self.method = method
        self.realm = realm
        self.fields = fields


    def checkPassword(self, password):
        """
        Verify that the credentials represented by this object agree with the
        given plaintext C{password} by hashing C{password} in the same way the
        response hash represented by this object was generated and comparing
        the results.
        """
        response = self.fields.get('response')
        uri = self.fields.get('uri')
        nonce = self.fields.get('nonce')
        cnonce = self.fields.get('cnonce')
        nc = self.fields.get('nc')
        algo = self.fields.get('algorithm', 'md5').lower()
        qop = self.fields.get('qop', 'auth')

        expected = calcResponse(
            calcHA1(algo, self.username, self.realm, password, nonce, cnonce),
            calcHA2(algo, self.method, uri, qop, None),
            algo, nonce, nc, cnonce, qop)

        return expected == response


    def checkHash(self, digestHash):
        """
        Verify that the credentials represented by this object agree with the
        credentials represented by the I{H(A1)} given in C{digestHash}.

        @param digestHash: A precomputed H(A1) value based on the username,
            realm, and password associate with this credentials object.
        """
        response = self.fields.get('response')
        uri = self.fields.get('uri')
        nonce = self.fields.get('nonce')
        cnonce = self.fields.get('cnonce')
        nc = self.fields.get('nc')
        algo = self.fields.get('algorithm', 'md5').lower()
        qop = self.fields.get('qop', 'auth')

        expected = calcResponse(
            calcHA1(algo, None, None, None, nonce, cnonce, preHA1=digestHash),
            calcHA2(algo, self.method, uri, qop, None),
            algo, nonce, nc, cnonce, qop)

        return expected == response



class DigestCredentialFactory(object):
    """
    Support for RFC2617 HTTP Digest Authentication

    @cvar CHALLENGE_LIFETIME_SECS: The number of seconds for which an
        opaque should be valid.

    @type privateKey: C{str}
    @ivar privateKey: A random string used for generating the secure opaque.

    @type algorithm: C{str}
    @param algorithm: Case insensitive string specifying the hash algorithm to
        use.  Must be either C{'md5'} or C{'sha'}.  C{'md5-sess'} is B{not}
        supported.

    @type authenticationRealm: C{str}
    @param authenticationRealm: case sensitive string that specifies the realm
        portion of the challenge
    """
    implements(ICredentialFactory)

    CHALLENGE_LIFETIME_SECS = 15 * 60    # 15 minutes

    scheme = "digest"

    def __init__(self, algorithm, authenticationRealm):
        self.algorithm = algorithm
        self.authenticationRealm = authenticationRealm
        self.privateKey = secureRandom(12)


    def generateNonce(self):
        """
        Create a random value suitable for use as the nonce parameter of a
        WWW-Authenticate challenge.

        @rtype: C{str}
        """
        return secureRandom(12).encode('hex')


    def _getTime(self):
        """
        Parameterize the time based seed used in generateOpaque
        so we can deterministically unittest it's behavior.
        """
        return time.time()


    def generateOpaque(self, nonce, clientip):
        """
        Generate an opaque to be returned to the client.  This is a unique
        string that can be returned to us and verified.
        """
        # Now, what we do is encode the nonce, client ip and a timestamp in the
        # opaque value with a suitable digest.
        now = str(int(self._getTime()))
        if clientip is None:
            clientip = ''
        key = "%s,%s,%s" % (nonce, clientip, now)
        digest = md5.new(key + self.privateKey).hexdigest()
        ekey = key.encode('base64')
        return "%s-%s" % (digest, ekey.strip('\n'))


    def verifyOpaque(self, opaque, nonce, clientip):
        """
        Given the opaque and nonce from the request, as well as the clientip
        that made the request, verify that the opaque was generated by us.
        And that it's not too old.

        @param opaque: The opaque value from the Digest response
        @param nonce: The nonce value from the Digest response
        @param clientip: The remote IP address of the client making the request
            or C{None} if the request was submitted over a channel where this
            does not make sense.

        @return: C{True} if the opaque was successfully verified.

        @raise error.LoginFailed: if C{opaque} could not be parsed or
            contained the wrong values.
        """
        # First split the digest from the key
        opaqueParts = opaque.split('-')
        if len(opaqueParts) != 2:
            raise error.LoginFailed('Invalid response, invalid opaque value')

        if clientip is None:
            clientip = ''

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

        try:
            when = int(keyParts[2])
        except ValueError:
            raise error.LoginFailed(
                'Invalid response, invalid opaque/time values')

        if (int(self._getTime()) - when >
            DigestCredentialFactory.CHALLENGE_LIFETIME_SECS):

            raise error.LoginFailed(
                'Invalid response, incompatible opaque/nonce too old')

        # Verify the digest
        digest = md5.new(key + self.privateKey).hexdigest()
        if digest != opaqueParts[0]:
            raise error.LoginFailed('Invalid response, invalid opaque value')

        return True


    def getChallenge(self, request):
        """
        Generate the challenge for use in the WWW-Authenticate header

        @param request: The L{IRequest} to with access was denied and for the
            response to which this challenge is being generated.

        @return: The C{dict} that can be used to generate a WWW-Authenticate
            header.
        """
        c = self.generateNonce()
        o = self.generateOpaque(c, request.getClientIP())

        return {'nonce': c,
                'opaque': o,
                'qop': 'auth',
                'algorithm': self.algorithm,
                'realm': self.authenticationRealm}


    def decode(self, response, request):
        """
        Decode the given response and attempt to generate a
        L{DigestedCredentials} from it.

        @type response: C{str}
        @param response: A string of comma seperated key=value pairs

        @type request: L{twisted.web2.server.Request}
        @param request: the request being processed

        @raise error.LoginFailed: If the response does not contain a username,
            a nonce, an opaque, or if the opaque is invalid.

        @return: L{DigestedCredentials}
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
                             request.getClientIP()):
            return DigestedCredentials(username,
                                       request.method,
                                       self.authenticationRealm,
                                       auth)
