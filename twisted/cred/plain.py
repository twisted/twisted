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

    def __init__(self, username, password, authzid=None):
        self.username = username
        self.password = password
        # Convert empty string to None
        self.authzid = authzid or None


    def checkPassword(self, password):
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

    def __init__(self, username, password, authzid=None):
        """
        Construct a digest responder. You can pass an optional default realm
        (e.g. a domain name for the username) which will be used if the server
        doesn't specify one.

        @param username: username to authenticate with.
        @type username: C{unicode}.

        @param password: password to authenticate with.
        @type password: C{unicode}.

        @param authzid: optional authorization ID.
        @type authzid: C{unicode}.
        """
        self.username = username
        self.password = password
        self.authzid = authzid


    def getInitialResponse(self, uri):
        return self._getResponse()


    def getResponse(self, challenge, uri):
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
            [self.authzid or "", self.username, self.password]))
        return resp



class SASLPlainChallenger(object):
    """
    An SASL PLAIN authentication challenger.
    """
    implements(sasl.ISASLChallenger)

    charset = 'utf-8'

    def __init__(self):
        pass


    def processResponse(self, response):
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
        return PlainCredentials(username, password, authzid)


    def getChallenge(self):
        return None


    def getSuccessfulChallenge(self, response, cred):
        return None


    def getRenewedChallenge(self, response):
        return None

