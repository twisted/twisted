# -*- test-case-name: twisted.test.test_newcred-*-

# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.


from zope.interface import implements, Interface

import hmac
import time
import random



class ICredentials(Interface):
    """
    I check credentials.

    Implementors _must_ specify which sub-interfaces of ICredentials
    to which it conforms, using zope.interface.implements().
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
        """Validate these credentials against the correct password.

        @param password: The correct, plaintext password against which to
        check.

        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
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
        """Validate these credentials against the correct password.

        @param password: The correct, plaintext password against which to
        check.

        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
        """



class IAnonymous(ICredentials):
    """
    I am an explicitly anonymous request for access.
    """



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
    I encapsulate an SSH public key to be checked against a users private
    key.

    @ivar username: Duh?

    @ivar algName: The algorithm name for the blob.

    @ivar blob: The public key blob as sent by the client.

    @ivar sigData: The data the signature was made from.

    @ivar signature: The signed data.  This is checked to verify that the user
    owns the private key.
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

