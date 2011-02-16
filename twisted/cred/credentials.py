# -*- test-case-name: twisted.test.test_newcred-*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from zope.interface import implements, Interface

import hmac, time, random
from twisted.python.hashlib import md5
from twisted.python.randbytes import secureRandom
from twisted.cred._digest import calcResponse, calcHA1, calcHA2
from twisted.cred import error

class ICredentials(Interface):
    """
    I check credentials.

    Implementors _must_ specify which sub-interfaces of ICredentials
    to which it conforms, using zope.interface.implements().
    """



class IUsernameDigestHash(ICredentials):
    """
    This credential is used when a CredentialChecker has access to the hash
    of the username:realm:password as in an Apache .htdigest file.
    """
    def checkHash(digestHash):
        """
        @param digestHash: The hashed username:realm:password to check against.

        @return: C{True} if the credentials represented by this object match
            the given hash, C{False} if they do not, or a L{Deferred} which
            will be called back with one of these values.
        """



class IUsernameHashedPassword(ICredentials):
    """
    I encapsulate a username and a hashed password.

    This credential is used when a hashed password is received from the
    party requesting authentication.  CredentialCheckers which check this
    kind of credential must store the passwords in plaintext (or as
    password-equivalent hashes) form so that they can be hashed in a manner
    appropriate for the particular credentials class.

    @type username: C{str}
    @ivar username: The username associated with these credentials.
    """

    def checkPassword(password):
        """
        Validate these credentials against the correct password.

        @type password: C{str}
        @param password: The correct, plaintext password against which to
        check.

        @rtype: C{bool} or L{Deferred}
        @return: C{True} if the credentials represented by this object match the
            given password, C{False} if they do not, or a L{Deferred} which will
            be called back with one of these values.
        """



class IUsernamePassword(ICredentials):
    """
    I encapsulate a username and a plaintext password.

    This encapsulates the case where the password received over the network
    has been hashed with the identity function (That is, not at all).  The
    CredentialsChecker may store the password in whatever format it desires,
    it need only transform the stored password in a similar way before
    performing the comparison.

    @type username: C{str}
    @ivar username: The username associated with these credentials.

    @type password: C{str}
    @ivar password: The password associated with these credentials.
    """

    def checkPassword(password):
        """
        Validate these credentials against the correct password.

        @type password: C{str}
        @param password: The correct, plaintext password against which to
        check.

        @rtype: C{bool} or L{Deferred}
        @return: C{True} if the credentials represented by this object match the
            given password, C{False} if they do not, or a L{Deferred} which will
            be called back with one of these values.
        """



class IAnonymous(ICredentials):
    """
    I am an explicitly anonymous request for access.
    """



class DigestedCredentials(object):
    """
    Yet Another Simple HTTP Digest authentication scheme.
    """
    implements(IUsernameHashedPassword, IUsernameDigestHash)

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

    CHALLENGE_LIFETIME_SECS = 15 * 60    # 15 minutes

    scheme = "digest"

    def __init__(self, algorithm, authenticationRealm):
        self.algorithm = algorithm
        self.authenticationRealm = authenticationRealm
        self.privateKey = secureRandom(12)


    def getChallenge(self, address):
        """
        Generate the challenge for use in the WWW-Authenticate header.

        @param address: The client address to which this challenge is being
        sent.

        @return: The C{dict} that can be used to generate a WWW-Authenticate
            header.
        """
        c = self._generateNonce()
        o = self._generateOpaque(c, address)

        return {'nonce': c,
                'opaque': o,
                'qop': 'auth',
                'algorithm': self.algorithm,
                'realm': self.authenticationRealm}


    def _generateNonce(self):
        """
        Create a random value suitable for use as the nonce parameter of a
        WWW-Authenticate challenge.

        @rtype: C{str}
        """
        return secureRandom(12).encode('hex')


    def _getTime(self):
        """
        Parameterize the time based seed used in C{_generateOpaque}
        so we can deterministically unittest it's behavior.
        """
        return time.time()


    def _generateOpaque(self, nonce, clientip):
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
        digest = md5(key + self.privateKey).hexdigest()
        ekey = key.encode('base64')
        return "%s-%s" % (digest, ekey.replace('\n', ''))


    def _verifyOpaque(self, opaque, nonce, clientip):
        """
        Given the opaque and nonce from the request, as well as the client IP
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
        digest = md5(key + self.privateKey).hexdigest()
        if digest != opaqueParts[0]:
            raise error.LoginFailed('Invalid response, invalid opaque value')

        return True


    def decode(self, response, method, host):
        """
        Decode the given response and attempt to generate a
        L{DigestedCredentials} from it.

        @type response: C{str}
        @param response: A string of comma seperated key=value pairs

        @type method: C{str}
        @param method: The action requested to which this response is addressed
        (GET, POST, INVITE, OPTIONS, etc).

        @type host: C{str}
        @param host: The address the request was sent from.

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
        if self._verifyOpaque(auth.get('opaque'), auth.get('nonce'), host):
            return DigestedCredentials(username,
                                       method,
                                       self.authenticationRealm,
                                       auth)



class CramMD5Credentials:
    implements(IUsernameHashedPassword)

    challenge = ''
    response = ''

    def __init__(self, host=None):
        self.host = host

    def getChallenge(self):
        if self.challenge:
            return self.challenge
        # The data encoded in the first ready response contains an
        # presumptively arbitrary string of random digits, a timestamp, and
        # the fully-qualified primary host name of the server.  The syntax of
        # the unencoded form must correspond to that of an RFC 822 'msg-id'
        # [RFC822] as described in [POP3].
        #   -- RFC 2195
        r = random.randrange(0x7fffffff)
        t = time.time()
        self.challenge = '<%d.%d@%s>' % (r, t, self.host)
        return self.challenge

    def setResponse(self, response):
        self.username, self.response = response.split(None, 1)

    def moreChallenges(self):
        return False

    def checkPassword(self, password):
        verify = hmac.HMAC(password, self.challenge).hexdigest()
        return verify == self.response


class UsernameHashedPassword:
    implements(IUsernameHashedPassword)

    def __init__(self, username, hashed):
        self.username = username
        self.hashed = hashed

    def checkPassword(self, password):
        return self.hashed == password


class UsernamePassword:
    implements(IUsernamePassword)

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def checkPassword(self, password):
        return self.password == password


class Anonymous:
    implements(IAnonymous)



class ISSHPrivateKey(ICredentials):
    """
    L{ISSHPrivateKey} credentials encapsulate an SSH public key to be checked
    against a user's private key.

    @ivar username: The username associated with these credentials.
    @type username: C{str}

    @ivar algName: The algorithm name for the blob.
    @type algName: C{str}

    @ivar blob: The public key blob as sent by the client.
    @type blob: C{str}

    @ivar sigData: The data the signature was made from.
    @type sigData: C{str}

    @ivar signature: The signed data.  This is checked to verify that the user
        owns the private key.
    @type signature: C{str} or C{NoneType}
    """



class SSHPrivateKey:
    implements(ISSHPrivateKey)
    def __init__(self, username, algName, blob, sigData, signature):
        self.username = username
        self.algName = algName
        self.blob = blob
        self.sigData = sigData
        self.signature = signature


class IPluggableAuthenticationModules(ICredentials):
    """I encapsulate the authentication of a user via PAM (Pluggable
    Authentication Modules.  I use PyPAM (available from
    http://www.tummy.com/Software/PyPam/index.html).

    @ivar username: The username for the user being logged in.

    @ivar pamConversion: A function that is called with a list of tuples
    (message, messageType).  See the PAM documentation
    for the meaning of messageType.  The function
    returns a Deferred which will fire with a list
    of (response, 0), one for each message.  The 0 is
    currently unused, but is required by the PAM library.
    """

class PluggableAuthenticationModules:
    implements(IPluggableAuthenticationModules)

    def __init__(self, username, pamConversion):
        self.username = username
        self.pamConversion = pamConversion

