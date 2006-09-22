# -*- test-case-name: twisted.web2.test.test_httpauth -*-

"""
Implementation of RFC2617: HTTP Digest Authentication

http://www.faqs.org/rfcs/rfc2617.html
"""

from twisted.cred import credentials, error
from zope.interface import implements

from twisted.web2.auth.interfaces import ICredentialFactory

import md5, sha
import random, sys

# The digest math

algorithms = {
    'md5': md5.md5,
    'md5-sess': md5.md5,
    'sha': sha.sha,
}

# DigestCalcHA1
def calcHA1(
    pszAlg,
    pszUserName,
    pszRealm,
    pszPassword,
    pszNonce,
    pszCNonce,
):
    
    m = algorithms[pszAlg]()
    m.update(pszUserName)
    m.update(":")
    m.update(pszRealm)
    m.update(":")
    m.update(pszPassword)
    HA1 = m.digest()
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
    hash = m.digest().encode('hex')
    return hash


class DigestedCredentials:
    """Yet Another Simple HTTP Digest authentication scheme"""

    implements(credentials.IUsernameHashedPassword)

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


class DigestCredentialFactory:
    implements(ICredentialFactory)

    CHALLENGE_LIFETIME = 15

    scheme = "digest"

    def __init__(self, algorithm, realm):
        """@type algorithm: C{str}
           @param algorithm: case insensitive string that specifies
              the hash algorithm used, should be either, md5, md5-sess
              or sha

           @type realm: C{str}
           @param realm: case sensitive string that specifies the realm
                         portion of the challenge
        """
        self.outstanding = {}
        self.algorithm = algorithm
        self.realm = realm

    def generateNonce(self):
        c = tuple([random.randrange(sys.maxint) for _ in range(3)])
        c = '%d%d%d' % c
        return c

    def generateOpaque(self):
        return str(random.randrange(sys.maxint))

    def getChallenge(self, peer):
        c = self.generateNonce()
        o = self.generateOpaque()
        self.outstanding[o] = c
        return {'nonce': c,
                'opaque': o,
                'qop': 'auth',
                'algorithm': self.algorithm,
                'realm': self.realm}

    def decode(self, response, request):
        def unq(s):
            if s[0] == s[-1] == '"':
                return s[1:-1]
            return s
        response = ' '.join(response.splitlines())
        parts = response.split(',')
        auth = dict([(k.strip(), unq(v.strip())) for (k, v) in [p.split('=', 1) for p in parts]])

        username = auth.get('username')
        if not username:
            raise error.LoginFailed('Invalid response, no username given')

        if auth.get('opaque') not in self.outstanding:
            raise error.LoginFailed('Invalid response, opaque not outstanding')

        del self.outstanding[auth['opaque']]
            
        return DigestedCredentials(username, request.method, self.realm, auth)
