# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Interfaces for SASL mechanisms as described in RFC 4422.

http://tools.ietf.org/html/rfc4422
"""

from zope.interface import Interface

from twisted.cred import credentials, error


class SASLError(error.LoginFailed):
    """
    A generic SASL error.
    """

class InvalidResponse(SASLError):
    """
    A response contains invalid (e.g. missing or mismatching) values.
    """

class InvalidChallenge(SASLError):
    """
    A challenge contains invalid (e.g. missing or mismatching) values.
    """

class FailedChallenge(SASLError):
    """
    Verification of an SASL challenge failed.
    (e.g. for a final Digest challenge with a wrong rspauth value).
    """

class UnexpectedFinalChallenge(InvalidChallenge):
    """
    A final challenge has been received but no response was previously sent.
    """


class IAuthzID(Interface):
    """
    I encapsulate an authorization ID.

    This credential is used when an authentication mechanism optionally
    provides an authorization ID as part as the authentication process.
    This authorization ID can be checked and used so as to decide which
    identity is requested.

    @type authzid: C{str} or None
    @ivar authzid: optional authorization ID.
    """

class ISASLCredentials(credentials.IUsernameHashedPassword, IAuthzID):
    """
    An SASL credential.
    """



# Design note: we could use singleton instances for ChallengeTypes returned
# by ISASLResponder.getResponse(), but we may want to add information to the
# returned instances in the future. For example, about the level of integrity
# provided, etc.

class ChallengeType(object):
    """
    An SASL challenge type.
    """

class InitialChallenge(ChallengeType):
    """
    An SASL initial challenge.
    """

class ChallengeRenewal(ChallengeType):
    """
    An SASL challenge renewal.
    """

class FinalChallenge(ChallengeType):
    """
    An SASL final challenge.
    """



class ISASLResponder(Interface):
    """
    An SASL responder responds to challenges sent by an SASL challenger speaking
    to us via an SASL-enabled protocol.
    """

    def getInitialResponse(uri):
        """
        Get the initial client response, if defined for this mechanism.

        @param uri: the protocol-dependent URI to authenticate against.
        @type uri: C{str}.
        @return: initial client response string, or None.
        @rtype: C{str}.
        """

    def getResponse(challenge, uri):
        """
        Process a server challenge.
        Returns a tuple of the challenge type and the response to be sent
        (if any).
        The challenge type gives the protocol a hint as to what policy to adopt:
        - if instance of InitialChallenge, there was no previous successful
          authentication. If it is the second InitialChallenge in a row, then
          perhaps it is time to ask the user another password.
        - if instance of ChallengeRenewal, the server refused the previous
          response because the challenge we responded to was too old. Sending a
          new response without re-asking for a password is recommended.
        - if instance of FinalChallenge, authentication was successful on both
          sides.

        @param challenge: server challenge.
        @type challenge: C{str}.
        @param uri: the protocol-dependent URI to authenticate against.
        @type uri: C{str}.
        @return: tuple of L{ChallengeType}, (C{str} or None).
        """


class ISASLChallenger(Interface):
    """
    An SASL challenger generates challenges and processes responses from a
    client.
    """

    def processResponse(response):
        """
        Process the response from the client and return credentials for checking
        the password. It can also return None if the challenge responded to is
        too old, in which case you'll have to generate a new one with
        getRenewedChallenge().

        @param challenge: server challenge.
        @type challenge: C{str}.
        @return: credentials.
        @rtype: L{ISASLCredentials}.
        """

    def getChallenge():
        """
        Get a challenge to send the client.

        @return: server challenge.
        @rtype: C{str}.
        """

    def getRenewedChallenge(response):
        """
        Get a renewed challenge to send the client (i.e. when received a
        response to an expired challenge).

        @param response: response received to the previous challenge.
        @type response: C{str}.
        @return: server challenge.
        @rtype: C{str}.
        """

    def getSuccessfulChallenge(response, credentials):
        """
        Get the final challenge, i.e. when auth when successful.
        Returns None if the particular SASL mechanism doesn't define a final
        challenge.

        @param response: latest successful response.
        @type response: C{str}.
        @param credentials: credentials of the successful response (as returned
            by processResponse()).
        @type credentials: L{ISASLCredentials}.
        @return: server challenge.
        @rtype: C{str}.
        """
