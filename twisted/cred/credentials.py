# -*- test-case-name: twisted.test.test_newcred-*-

from twisted.python import components
from twisted.python import util

import hmac
import time
import random

try:
    import crypt
except ImportError:
    crypt = None

class ICredentials(components.Interface):
    """I check credentials.

    @cvar __implements__: Implementors _must_ provide an __implements__
    attribute which contains at least the list of sub-interfaces of
    ICredentials to which it conforms.
    """


class IUsernameHashedPassword(ICredentials):
    """I encapsulate a username and a hashed password.
    
    This credential is used when a hashed password is received from the
    party requesting authentication.  CredentialCheckers which check
    this kind of credential must store the passwords in plaintext form
    so that they can be hashed in a manner appropriate for the particular
    credentials class.
    
    @type username: C{str} or C{Deferred}
    @ivar username: The username associated with these credentials.
    """
    
    def checkPassword(self, password):
        """Validate these credentials against the correct password.
        
        @param password: The correct, plaintext password against which to
        @check.
        
        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
        """


class IUsernamePassword(ICredentials):
    """I encapsulate a username and a plaintext password.
    
    This encapsulates the case where the password received over the network
    has been hashed with the identity function (That is, not at all).  The
    CredentialsChecker may store the password in whatever format it desires,
    it need only transform the stored password in a similar way before
    performing the comparison.

    @type username: C{str} or C{Deferred}
    @ivar username: The username associated with these credentials.
    
    @type password: C{str} or C{Deferred}
    @ivar password: The password associated with these credentials.
    """

    def checkPassword(self, password):
        """Validate these credentials against the correct password.
        
        @param password: The correct, plaintext password against which to
        check.
        
        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
        """

class IAnonymous(ICredentials):
    """I am an explicitly anonymous request for access.
    """


class SimpleMD5ChallengeResponse(ICredentials):
    """XXX specify PB c/r protocol
    """

class CramMD5Credentials:
    __implements__ = (IUsernameHashedPassword,)

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

    def checkPassword(self, password):
        verify = hmac.HMAC(password, self.challenge).hexdigest()
        return verify == self.response

class UsernameHashedPassword:
    __implements__ = (IUsernameHashedPassword,)

    def __init__(self, username, hashed):
        self.username = username
        self.hashed = hashed

    def checkPassword(self, password):
        return self.hashed == password

class UsernamePassword:
    __implements__ = (IUsernamePassword,)

    def __init__(self, username, password):
        self.username = username
        self.password = password
    
    def checkPassword(self, password):
        return self.password == password

class Anonymous:
    __implements__ = (IAnonymous,)
