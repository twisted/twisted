# -*- test-case-name: twisted.test.test_digest -*-
# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of RFC 2617: HTTP Digest Authentication
and RFC 2831: Digest Authentication as a SASL Mechanism,
with support for RFC 2069 (obsoleted by RFC 2617).

http://tools.ietf.org/html/rfc2617
http://tools.ietf.org/html/rfc2831
http://tools.ietf.org/html/rfc2069
"""

import time
import md5
import sha
import weakref

from zope.interface import implements, Interface, Attribute

from twisted.cred import sasl
from twisted.internet import reactor
from twisted.python.randbytes import secureRandom

try:
    set
except NameError:
    from sets import Set as set


DEFAULT_METHOD = "AUTHENTICATE"
DEFAULT_BODY_HASH = "0" * 32



# Fields which shouldn't be quoted
_unquotedFields = set(["algorithm", "nc", "stale", "response", "rspauth"])


def _parseDigest(digestString):
    """
    Parses a digest challenge or response.
    """
    s = digestString
    paramDict = {}
    cur = 0
    remainingParams = True
    while remainingParams:
        # Parse a param. We can't just split on commas, before there can be
        # some commas inside (quoted) param values, e.g.: qop="auth,auth-int"
        middle = s.index("=", cur)
        name = s[cur:middle].lstrip()
        middle += 1
        if s[middle] == '"':
            middle += 1
            end = s.index('"', middle)
            value = s[middle:end]
            cur = s.find(',', end) + 1
            if cur == 0:
                remainingParams = False
        else:
            end = s.find(',', middle)
            if end == -1:
                value = s[middle:].rstrip()
                remainingParams = False
            else:
                value = s[middle:end].rstrip()
            cur = end + 1
        paramDict[name] = value
    return paramDict



def parseChallenge(challenge):
    """
    Parses a digest challenge.

    @param challenge: the string representation of the digest challenge.
    @type challenge: C{str}.

    @return: dictionary of parsed fields.
    @rtype: C{dict}.
    """
    fields = _parseDigest(challenge)
    if 'qop' in fields:
        fields['qop'] = fields['qop'].split(',')
    else:
        fields['qop'] = []
    fields['stale'] = (fields.get('stale') == "true")
    return fields



def parseResponse(response):
    """
    Parses a digest response.

    @param response: the string representation of the digest response.
    @type response: C{str}.

    @return: dictionary of parsed fields.
    @rtype: C{dict}.
    """
    return _parseDigest(response)



def _unparseDigest(**fields):
    """
    Generate the string representation of a digest challenge or response.
    """
    q = _unquotedFields
    s = ", ".join([(k in q and '%s=%s' or '%s="%s"') % (k, v)
                    for (k, v) in fields.iteritems() if v])
    return s



def unparseChallenge(**fields):
    """
    Generate the string representation of a digest challenge.

    @param fields: dictionary of fields.
    @type fields: C{dict}.

    @return: string representation of the challenge.
    @rtype: C{str}.
    """
    qop = fields.pop('qop', None)
    if qop:
        fields['qop'] = ','.join(qop)
    if fields.pop('stale', False):
        fields['stale'] = 'true'
    return _unparseDigest(**fields)



def unparseResponse(**fields):
    """
    Generate the string representation of a digest response.

    @param fields: dictionary of fields.
    @type fields: C{dict}.

    @return: string representation of the response.
    @rtype: C{str}.
    """
    return _unparseDigest(**fields)


# The digest math

algorithms = {
    'md5': md5.new,
    'md5-sess': md5.new,
    'sha': sha.new,
}



def calcHA1(pszAlg, pszUserName, pszRealm, pszPassword, pszNonce, pszCNonce,
            pszAuthzID=None, preHA1=None):
    """
    @param pszAlg: The name of the algorithm to use to calculate the digest.
        Currently supported are md5 md5-sess and sha.

    @param pszUserName: The username

    @param pszRealm: The realm

    @param pszPassword: The password

    @param pszNonce: The nonce

    @param pszCNonce: The cnonce

    @param pszAuthzID: The optional authzid (or None)

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
        if pszAuthzID:
            m.update(":")
            m.update(pszAuthzID)
        HA1 = m.digest()

    return HA1.encode('hex')



def calcDigestHash(pszAlg, pszUserName, pszRealm, pszPassword):
    """
    Calculate the hash of username/realm/password using the algorithm specified
    in C{pszAlg}.
    """
    m = algorithms[pszAlg]()
    m.update(pszUserName)
    m.update(":")
    m.update(pszRealm)
    m.update(":")
    m.update(pszPassword)
    return m.hexdigest()



def calcResponse(HA1, algo, pszNonce, pszNonceCount, pszCNonce, pszQop,
                 pszMethod, pszDigestUri, pszHEntity):
    """
    Build the response hash in response of a challenge.
    """
    m = algorithms[algo]()
    m.update(pszMethod)
    m.update(":")
    m.update(pszDigestUri)
    if pszQop == "auth-int" or pszQop == "auth-conf":
        m.update(":")
        m.update(pszHEntity)
    HA2 = m.hexdigest()

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
    return m.hexdigest()



class IDigestMechanism(Interface):
    """
    A Digest mechanism.
    """

    digestURIFieldName = Attribute("""name of the digest URI field""")
    algorithm = Attribute("""name of digest algorithm""")

    def setClientParams(cnonce, nc, qop, realm=None):
        """
        Set the client-supplied digest parameters.

        @param cnonce: the cnonce parameter.
        @type cnonce: C{str}.

        @param nc: the nonce-count parameter.
        @type nc: C{str}.

        @param qop: the qop parameter (can be C{None} for old-school Digest
            auth).
        @type qop: C{str}.

        @param realm: the realm parameter (can be C{None} if the server
            supplies one).
        @type realm: C{str}.
        """


    def getDigestHash(password):
        """
        Get the digest hash from a clear-text password.

        @param password: the clear-text password.
        @type password: C{str}.

        @return: the digest hash, in hexadecimal form.
        @rtype: C{str}.
        """


    def getResponseFromPassword(password, method=None, bodyHash=None):
        """
        Get the digest response from a clear-text password.

        @param password: the clear-text password.
        @type password: C{str}.

        @param method: optional method name for integrity checking.
        @type method: C{str}.

        @param bodyHash: optional hash of the message body for integrity
            checking.
        @type bodyHash: C{str}.

        @return: digest response in hexadecimal form.
        @rtype: C{str}.
        """


    def getResponseFromDigestHash(digestHash, method=None, bodyHash=None):
        """
        Get the digest response from a pre-computed digest hash
        (a hash of "username:realm:password").

        @param digestHash: the pre-computed digest hash in hexadecimal form.
        @type digestHash: C{str}.

        @param method: optional method name for integrity checking.
        @type method: C{str}.

        @param bodyHash: optional hash of the message body for integrity
            checking.
        @type bodyHash: C{str}.

        @return: digest response in hexadecimal form.
        @rtype: C{str}.
        """



class BaseDigestMechanism(object):
    """
    Base class for all authentication mechanim using digest.
    """

    def __init__(self, username, uri, fields, authzid=None, algorithm=None):
        """
        @param username: the user used in the challenge.
        @type username: C{str} or C{unicode}

        @param uri: challenge uri.
        @type uri: C{str}

        @param fields: infos extracted from the challenge.
        @type fields: C{dict}

        @param authzid: optional authentication id.
        @type authzid: C{str}

        @param algorithm: optional digest algorithm to use.
        @type algorithm: C{str}
        """
        self.charset = 'charset' in fields and 'utf-8' or 'iso-8859-1'
        self.username = username
        self.uri = uri
        self.authzid = authzid

        self.nonce = fields.get('nonce')
        self.realm = fields.get('realm')
        self.algorithm = algorithm or self._guessAlgorithm(fields)

        self.lastDigestHash = None


    def _guessAlgorithm(self, fields):
        """
        Specify an algorithm for this mecanism, using the C{fields} if
        necessary.
        """
        raise NotImplementedError()


    def setClientParams(self, cnonce, nc, qop, realm=None):
        """
        Set the client-supplied digest parameters.
        """
        self.cnonce = cnonce
        self.nc = nc
        self.qop = qop
        if realm:
            self.realm = realm


    def getBodyHash(self, body=None):
        """
        Return the hash of the specified body, if necessary.
        """
        if self.qop == "auth-int" and body is not None:
            hashAlg = algorithms[self.algorithm]
            bodyHash = hashAlg(body).hexdigest()
        else:
            bodyHash = None
        return bodyHash


    def getDigestHash(self, password):
        """
        Build hash of the password, using previously saved username, realm and
        algorithm.
        """
        username, password = self.specialEncode(self.username, password)
        return calcDigestHash(self.algorithm, username, self.realm, password)


    def getResponseFromPassword(self, password, method=None, bodyHash=None):
        """
        Build the hash response from a password.
        """
        digestHash = self.getDigestHash(password)
        return self.getResponseFromDigestHash(digestHash, method, bodyHash)


    def getResponseFromDigestHash(self, digestHash, method=None, bodyHash=None):
        """
        Build the hash response from a previous digest hash.
        """
        if method is None:
            method = DEFAULT_METHOD
        bodyHash = bodyHash or DEFAULT_BODY_HASH
        self.lastDigestHash = digestHash
        return calcResponse(
            calcHA1(self.algorithm, None, None, None, self.nonce, self.cnonce,
                pszAuthzID=self.authzid, preHA1=digestHash),
            self.algorithm, self.nonce, self.nc, self.cnonce, self.qop, method,
            self.uri, bodyHash)


    def encode(self, s):
        """
        If the argument is an unicode string, encode it according to the stored
        charset parameter.

        @param s: string to be encoded.
        @type s: C{str} or C{unicode}.

        @return: encoded string.
        @rtype: C{str}.
        """
        if isinstance(s, unicode):
            return s.encode(self.charset)
        return s


    def specialEncode(self, *strings):
        """
        Apply the special encoding algorithm as defined in RFC 2831 to the
        given strings: if the stored charset parameter is utf-8 and all the
        strings can be encoded to iso-8859-1, then encode them into iso-8859-1.
        Otherwise, encode them according to the stored charset parameter.

        @param strings: strings to be encoded.
        @type strings: sequence of C{unicode} or C{str}.

        @return: list of encoded strings.
        @rtype: sequence of C{str}.
        """
        def _encode(charset):
            return [isinstance(s, unicode) and s.encode(charset) or s
                for s in strings]
        if self.charset == 'utf-8':
            try:
                return _encode('iso-8859-1')
            except UnicodeEncodeError:
                pass
        return _encode(self.charset)



class SASLDigestMechanism(BaseDigestMechanism):
    """
    The SASL Digest mechanism (as per RFC 2831).
    """
    implements(IDigestMechanism)
    digestURIFieldName = "digest-uri"

    def _guessAlgorithm(self, fields):
        """
        The digest algorith is fixed to C{md5-sess}.
        """
        return "md5-sess"



class HTTPDigestMechanism(BaseDigestMechanism):
    """
    The HTTP Digest mechanism (as per RFC 2617).
    """
    implements(IDigestMechanism)
    digestURIFieldName = "uri"

    def _guessAlgorithm(self, fields):
        """
        Get the algorithm for the C{fields}, with default to C{md5}.
        """
        return fields.get('algorithm', 'MD5').lower()



# TODO: add IIntegrityChecker for the "auth-int" case

class IUsernameDigestHash(Interface):
    """
    This credential is used when a CredentialChecker has access to the hash
    of the username:realm:password as in an Apache .htdigest file.
    """

    def checkHash(digestHash):
        """
        @param digestHash: The hashed username:realm:password to check against.

        @return: a deferred which becomes, or a boolean indicating if the
            hash matches.
        """



class DigestedCredentials(object):
    """
    Credentials from a SASL Digest response.
    """

    implements(sasl.ISASLCredentials, IUsernameDigestHash)

    def __init__(self, mechanism, response, method=None, bodyHash=None):
        """
        @param mechanism: instance of a digest mechanism.
        @type mechanism: provider of C{IDigestMechanism}

        @param response: expected response of the challenge.
        @type response: C{str}

        @param method: optional method name for integrity checking.
        @type method: C{str}

        @param bodyHash: optional hash of the body.
        @type bodyHash: C{str}
        """
        self.mechanism = mechanism
        self.username = self.mechanism.username
        self.authzid = self.mechanism.authzid
        self.response = response
        self.method = method
        self.bodyHash = bodyHash
        self.rspauth = None


    def checkPassword(self, password):
        """
        Check if password match: calculate its hash and compare it to the
        expected value.
        """
        digestHash = self.mechanism.getDigestHash(password)
        return self.checkHash(digestHash)


    def checkHash(self, digestHash):
        """
        Check the integrity of the hash against the expected one.
        """
        expected = self.mechanism.getResponseFromDigestHash(
            digestHash, self.method, self.bodyHash)
        if expected == self.response:
            # rspauth is generated by using the same parameters, except method
            # which is the empty string.
            # XXX I'm not sure if the bodyHash is the current one or the one
            # for the message containing the successful challenge.
            # The distinction is irrelevant for SASL but not for HTTP.
            self.rspauth = self.mechanism.getResponseFromDigestHash(
                digestHash, "", self.bodyHash)
            return True
        return False



class BaseDigestResponder(object):
    """
    Base class for digest responder.
    """

    def __init__(self, username, password, realm=None, authzid=None):
        """
        Construct a digest responder. You can pass an optional default realm
        (e.g. a domain name for the username) which will be used if the server
        doesn't specify one.

        @param username: username to authenticate with.
        @type username: C{str} or C{unicode}.

        @param password: password to authenticate with.
        @type password: C{str} or C{unicode}.

        @param realm: optional realm.
        @type realm: C{str}.

        @param authzid: optional authorization ID.
        @type authzid: C{str}.
        """
        self.username = username
        self.password = password
        self.realm = realm
        self.authzid = authzid
        self.cnonce = None
        self.nonceCount = 1
        self.prevNonce = None
        self.lastMechanism = None


    def getResponse(self, challenge, uri, method=None, body=None):
        """
        Process a server challenge.
        Returns a tuple of the challenge type and the response to be sent
        (if any). The challenge type gives the protocol a hint as to what
        policy to adopt:
            - if instance of InitialChallenge, there was no previous successful
              authentication. If it is the second InitialChallenge in a row,
              then perhaps it is time to ask the user another password.
            - if instance of ChallengeRenewal, the server refused the previous
              response because the challenge we responded to was too old.
              Sending a new response without re-asking for a password is
              recommended.
            - if instance of FinalChallenge, authentication was successful on
              both sides.

        @param challenge: server challenge.
        @type challenge: C{str}.

        @param uri: the URI to authenticate against.
        @type uri: C{str}.

        @param method: optional method for message integrity.
        @type method: C{str}.

        @param body: optional body for message integrity.
        @type body: C{str}.

        @return: tuple of L{ChallengeType}, (C{str} or None).
        """
        f = parseChallenge(challenge)
        rspauth = f.get('rspauth')
        if rspauth:
            # Final challenge: rspauth will be checked with the same parameters
            # as the previous response
            chalType = sasl.FinalChallenge()
            method = ""
            mechanism = self.lastMechanism
            if not mechanism:
                raise sasl.UnexpectedFinalChallenge("Unexpected final challenge.")
        else:
            # Non-final challenge: extract parameters and build mechanism
            realm = f.get('realm') or self.realm
            if not realm:
                raise sasl.InvalidChallenge("Missing realm value.")
            if f['stale']:
                chalType = sasl.ChallengeRenewal()
            else:
                chalType = sasl.InitialChallenge()

            mechanism = self.mechanismClass(username=self.username,
                uri=uri, fields=f, authzid=self.authzid)

            qop = self._chooseQop(f['qop'], method, body)
            nonce = f['nonce']
            if qop:
                cnonce = self.cnonce
                if cnonce is None:
                    cnonce = sha.new(secureRandom(20)).hexdigest()
                    self.cnonce = cnonce
                # XXX is this robust enough?
                if nonce == self.prevNonce:
                    self.nonceCount += 1
                else:
                    self.nonceCount = 1
                    self.prevNonce = nonce
                nc = "%08X" % self.nonceCount
            else:
                # Fallback on old-school Digest mechanism
                cnonce = None
                nc = None
            mechanism.setClientParams(cnonce, nc, qop, realm)
            self.lastMechanism = mechanism

        bodyHash = mechanism.getBodyHash(body)
        digestResponse = mechanism.getResponseFromPassword(self.password,
                                                           method, bodyHash)

        if rspauth:
            if rspauth != digestResponse:
                raise sasl.FailedChallenge(
                    "Invalid final challenge: wrong rspauth value.")
            return chalType, None

        respFields = {
            'username': mechanism.encode(self.username),
            'realm' : mechanism.realm,
            'nonce' : nonce,
            'cnonce' : cnonce,
            'nc' : nc,
            'qop' : qop,
            mechanism.digestURIFieldName: uri,
            'response': digestResponse,
        }
        for s in 'charset', 'opaque':
            if s in f:
                respFields[s] = f[s]
        if self.authzid:
            respFields['authzid'] = self.authzid
        return chalType, unparseResponse(**respFields)


    def _chooseQop(self, chalQops, method=None, body=None):
        """
        Decide of the Quality Of Protection to use for a specific response.
        """
        # XXX factor out choice of qop in concrete mechanism?
        if "auth-int" in chalQops and (body is not None or
                                       "auth" not in chalQops):
            return "auth-int"
        elif "auth" in chalQops:
            return "auth"
        else:
            return None



class SASLDigestResponder(BaseDigestResponder):
    """
    An SASL Digest authentication responder.
    """
    implements(sasl.ISASLResponder)
    mechanismClass = SASLDigestMechanism

    def getInitialResponse(self, uri):
        """
        Initial response of SASL digest doesn't exist.
        """
        return None


    # Override method to have the correct signature (without optional arguments)
    def getResponse(self, challenge, uri):
        return BaseDigestResponder.getResponse(self, challenge, uri)



class HTTPDigestResponder(BaseDigestResponder):
    """
    An HTTP Digest authentication responder.
    """
    mechanismClass = HTTPDigestMechanism



class NonceSlot(object):
    """
    Contains a nonce-count, an IDelayedCall and a weakref to its creator.
    """

    def __init__(self, dc, container):
        """
        @param dc: a call to cancel when container disappear.
        @type dc: C{DelayedCall}

        @param container: the object responsible for the lifetime of the nonce.
        @type container: any
        """
        self.nc = 0
        def _destroyed(_, dc=dc):
            if dc.active():
                dc.cancel()
        self._ref = weakref.ref(container, _destroyed)



class BaseDigestChallenger(object):
    """
    Basic class of digest challenger.
    """
    CHALLENGE_LIFETIME_SECS = 15 * 60    # 15 minutes

    _callLater = reactor.callLater

    def __init__(self, realm=None):
        """
        @param realm: case sensitive string that specifies the realm portion
            of the challenge. If None, any realm will be accepted.
        @type realm: C{str}
        """
        self.realm = realm
        self.nonces = {}


    def processResponse(self, response, method=None, body=None):
        """
        Process the response from the client and return credentials for
        checking the password. It can also return None if the challenge
        responded to is too old, in which case you'll have to generate a new
        one with getRenewedChallenge().

        @param challenge: server challenge.
        @type challenge: C{str}.

        @param method: optional method for message integrity.
        @type method: C{str}.

        @param body: optional body for message integrity.
        @type body: C{str}.

        @return: credentials.
        @rtype: L{twisted.cred.credentials.IUsernameHashedPassword}.
        """
        f = parseResponse(response)
        nonce = f.get('nonce')
        if not nonce:
            raise sasl.InvalidResponse('Missing once.')
        realm = f.get('realm')
        if self.realm and realm != self.realm:
            raise sasl.InvalidResponse("Invalid realm '%s'" % realm)
        username = f.get('username')
        if not username:
            raise sasl.InvalidResponse("Missing username.")
        digestResponse = f.get('response')
        if not digestResponse:
            raise sasl.InvalidResponse("Missing digest response.")
        digestURI = f.get('digest-uri') or f.get('uri')
        if not digestURI:
            raise sasl.InvalidResponse("Missing digest URI.")
        cnonce = f.get('cnonce')
        nc = f.get('nc')
        qop = f.get('qop')
        if not qop and not self.acceptWeakDigest:
            raise sasl.InvalidResponse("Missing qop value")
        if qop and qop != "auth" and qop != "auth-int":
            raise sasl.InvalidResponse("Invalid qop value '%s'" % qop)
        if qop and (not nc or not cnonce):
            raise sasl.InvalidResponse("Missing nc and/or cnonce value.")
        algo = f.get('algorithm')
        if algo and algo != self.algorithm:
            raise sasl.InvalidResponse("Invalid algorithm '%s'" % algo)
        authzid = f.get('authzid')

        if not self.acceptNonce(nonce, nc or None):
            return None

        mechanism = self.mechanismClass(username=username, authzid=authzid,
            uri=digestURI, fields=f, algorithm=self.algorithm)
        mechanism.setClientParams(cnonce, nc, qop)

        bodyHash = mechanism.getBodyHash(body)
        return DigestedCredentials(mechanism, digestResponse, method, bodyHash)


    def getChallenge(self):
        """
        Get a challenge to send the client.

        @return: server challenge.
        @rtype: C{str}.
        """
        f = self._getAuthChallenge()
        return unparseChallenge(**f)


    def getSuccessfulChallenge(self, response, cred):
        """
        Get the final challenge, i.e. when auth when successful.
        Returns C{None} if the particular SASL mechanism doesn't define a final
        challenge.

        @param response: latest successful response.
        @type response: C{str}.

        @param response: credentials of the successful response (as returned by
            processResponse()).
        @type response: L{twisted.cred.credentials.IUsernameHashedPassword}.

        @return: server challenge.
        @rtype: C{str}.
        """
        # XXX we assume that cred is an instance of DigestedCredentials,
        # and that cred.rspauth is not None.
        if not cred.mechanism.qop:
            # No rspauth for RFC 2069, don't bother with nextnonce et al.
            return None
        f = { 'rspauth': cred.rspauth }
        return unparseChallenge(**f)


    def getRenewedChallenge(self, response):
        """
        Get a renewed challenge to send the client (i.e. when received a
        response to an expired challenge).

        @param response: response received to the previous challenge.
        @type response: C{str}.
        @return: server challenge.
        @rtype: C{str}.
        """
        f = self._getAuthChallenge()
        f['stale'] = True
        return unparseChallenge(**f)


    def generateNonce(self):
        """
        Generate a nonce to be sent as part of the challenge.
        This is an unique string that can be returned to us and verified, but
        unpredictable by an attacker.

        @return: nonce.
        @rtype: C{str}.
        """
        while True:
            nonce = "%d.%s" % (self._getTime(),
                               sha.new(secureRandom(20)).hexdigest())
            if nonce not in self.nonces:
                break
        # The following function object must not contain any reference to self
        def _nonceExpired(nonces, nonce):
            del nonces[nonce]
        dc = self._callLater(self.CHALLENGE_LIFETIME_SECS, _nonceExpired,
            self.nonces, nonce)
        self.nonces[nonce] = NonceSlot(dc, self)
        return nonce


    def acceptNonce(self, nonce, nc=None):
        """
        Given the nonce from the client response, verify that the nonce is
        fresh enough and that the nonce-count is appropriate.
        Returns C{True} if the nonce is accepted, C{False} if the challenge is
        not fresh enough, and raises an error if the nonce or nonce-count is
        invalid (e.g. faked).
        If C{True} is returned, the nc value is eaten and trying to reuse it
        will raise an error (protection against replays).

        This method is implicitly called by processResponse().

        @param nonce: nonce value from the Digest response
        @type nonce: C{str}.

        @param nc: nonce-count value from the Digest response
        @type nc: C{str}.

        @return: True if the nonce is fresh enough.
        @rtype: C{bool}.

        @raise sasl.InvalidResponse: if the nonce is invalid and the
            authentication should fail.
        """
        try:
            timestamp, seed = nonce.split(".")
            timestamp = int(timestamp)
        except ValueError:
            raise sasl.InvalidResponse("Invalid nonce value")

        age = self._getTime() - timestamp
        if age > self.CHALLENGE_LIFETIME_SECS - 1:
            return False
        if age < 0:
            raise sasl.InvalidResponse("Invalid nonce value")

        # We check the nc only if the nonce is fresh, because otherwise the
        # entry in self.nonces will have been deleted.
        nonceSlot = self.nonces.get(nonce)
        if nonceSlot is None:
            raise sasl.InvalidResponse("Invalid nonce value.")
        if nc is not None:
            if int(nc, 16) != nonceSlot.nc + 1:
                raise sasl.InvalidResponse("Invalid nc value.")
            nonceSlot.nc += 1

        return True


    def _getAuthChallenge(self):
        """
        Build challenge fields.
        """
        nonce = self.generateNonce()
        f = {
            'nonce': nonce,
            'qop': ['auth', 'auth-int'],
            'algorithm': self.algorithm,
        }
        if self.realm:
            f['realm'] = self.realm
        self._populateChallenge(f)
        return f


    def _getTime(self):
        """
        Parameterize the time based seed used in _generateNonce()
        so we can deterministically unittest it's behavior.
        """
        return time.time()



class SASLDigestChallenger(BaseDigestChallenger):
    """
    An SASL Digest challenger generates challenges and processes responses from a client.
    """
    implements(sasl.ISASLChallenger)
    mechanismClass = SASLDigestMechanism
    acceptWeakDigest = False
    algorithm = "md5-sess"

    # Override method to have the correct signature (without optional arguments)
    def processResponse(self, response):
        return BaseDigestChallenger.processResponse(self, response)


    def _populateChallenge(self, fields):
        """
        Populate the challenge fields: the charset must be forced to utf-8.
        """
        fields['charset'] = 'utf-8'



class HTTPDigestChallenger(BaseDigestChallenger):
    """
    An HTTP Digest challenger generates challenges and processes responses from a client.
    """
    mechanismClass = HTTPDigestMechanism
    # Required to support RFC 2069-only clients
    acceptWeakDigest = True
    algorithm = "md5"


    def _populateChallenge(self, fields):
        """
        Populate the challenge fields: set opaque to false.
        """
        fields['opaque'] = '0'

