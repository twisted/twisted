# -*- test-case-name: twisted.web.test.test_httpauth -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP BASIC authentication.

@see: U{http://tools.ietf.org/html/rfc1945}
@see: U{http://tools.ietf.org/html/rfc2616}
@see: U{http://tools.ietf.org/html/rfc2617}
"""

import binascii

from zope.interface import implements

from twisted.cred import credentials, error
from twisted.web.iweb import ICredentialFactory


class BasicCredentialFactory(object):
    """
    Credential Factory for HTTP Basic Authentication

    @type authenticationRealm: C{str}
    @ivar authenticationRealm: The HTTP authentication realm which will be issued in
        challenges.
    """
    implements(ICredentialFactory)

    scheme = 'basic'

    def __init__(self, authenticationRealm):
        self.authenticationRealm = authenticationRealm


    def getChallenge(self, request):
        """
        Return a challenge including the HTTP authentication realm with which
        this factory was created.
        """
        return {'realm': self.authenticationRealm}


    def decode(self, response, request):
        """
        Parse the base64-encoded, colon-separated username and password into a
        L{credentials.UsernamePassword} instance.
        """
        try:
            creds = binascii.a2b_base64(response + '===')
        except binascii.Error:
            raise error.LoginFailed('Invalid credentials')

        creds = creds.split(':', 1)
        if len(creds) == 2:
            return credentials.UsernamePassword(*creds)
        else:
            raise error.LoginFailed('Invalid credentials')
