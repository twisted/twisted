# -*- test-case-name: twisted.test.test_plain -*-
# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of RFC 4616: PLAIN SASL Mechanism.

http://tools.ietf.org/html/rfc4616
"""

from zope.interface import implements

from twisted.cred import credentials, sasl



class PlainCredentials(object):
    """
    Credentials from a SASL PLAIN response.
    """

    implements(credentials.IUsernamePassword, sasl.ISASLCredentials)

    def __init__(self, username, password):
        """
        @param username: the login of the user.
        @type username: C{unicode}

        @param password: the password of the user.
        @type password: C{unicode}
        """
        self.username = username
        self.password = password


    def checkPassword(self, password):
        """
        Check the validity of the plain password agains the expected one.
        """
        return password == self.password



class SASLPlainResponder(object):
    """
    An SASL PLAIN authentication responder.

    @cvar charset: the charset for conversion to/from unicode (should be
        'utf-8')
    @type charset: C{str}
    """
    implements(sasl.ISASLResponder)

    charset = 'utf-8'

    def __init__(self, username, password):
        """
        Construct a digest responder. You can pass an optional default realm
        (e.g. a domain name for the username) which will be used if the server
        doesn't specify one.

        @param username: username to authenticate with.
        @type username: C{unicode}.

        @param password: password to authenticate with.
        @type password: C{unicode}.
        """
        self.username = username
        self.password = password


    def getInitialResponse(self, uri):
        """
        Build the initial response.
        """
        return self._getResponse()


    def getResponse(self, challenge, uri):
        """
        Build the challenge initialization.
        """
        resp = self._getResponse()
        return sasl.InitialChallenge(), resp


    def _getResponse(self):
        """
        Compute the actual PLAIN authentication string.

        @return: authentication string.
        @rtype: C{str}.
        """
        # XXX add support for authentication without authzid?
        # (seen in twisted.mail.smtp)
        resp = "\0".join(map(lambda s: s.encode(self.charset),
            ["", self.username, self.password]))
        return resp



class SASLPlainChallenger(object):
    """
    An SASL PLAIN authentication challenger.
    """
    implements(sasl.ISASLChallenger)

    charset = 'utf-8'

    def processResponse(self, response):
        """
        Parse SASL response and build credentials from it.
        """
        try:
            authzid, username, password = response.split('\0')
        except ValueError:
            raise sasl.InvalidResponse("Invalid SASL PLAIN response.")
        if not username:
            raise sasl.InvalidResponse("Missing username.")
        # XXX should we allow an empty password?
        if not password:
            raise sasl.InvalidResponse("Missing password.")
        try:
            authzid, username, password = map(lambda s: s.decode(self.charset),
                [authzid, username, password])
        except UnicodeDecodeError:
            raise sasl.InvalidResponse(
                "Cannot decode SASL PLAIN response to %s." % self.charset)
        return PlainCredentials(username, password)


    def getChallenge(self):
        """
        There is no challenge in PLAIN authentication.
        """
        return None


    def getSuccessfulChallenge(self, response, cred):
        """
        There is no successfull challenge in PLAIN authentication.
        """
        return None


    def getRenewedChallenge(self, response):
        """
        There is no renewed challenge in PLAIN authentication.
        """
        return None

