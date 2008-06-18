# -*- test-case-name: twisted.web.test -*-
# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interface definitions for L{twisted.web}.
"""

from zope.interface import Interface, Attribute


class ICredentialFactory(Interface):
    """
    A credential factory defines a way to generate a particular kind of
    authentication challenge and a way to interpret the responses to these
    challenges.  It creates L{ICredentials} providers from responses.  These
    objects will be used with L{twisted.cred} to authenticate an authorize
    requests.
    """
    scheme = Attribute(
        "A C{str} giving the name of the authentication scheme with which "
        "this factory is associated.  For example, C{'basic'} or C{'digest'}.")


    def getChallenge(request):
        """
        Generate a new challenge to be sent to a client.

        @type peer: L{twisted.web.http.Request}
        @param peer: The request the response to which this challenge will be
            included.

        @rtype: C{dict}
        @return: A mapping from C{str} challenge fields to associated C{str}
            values.
        """


    def decode(response, request):
        """
        Create a credentials object from the given response.

        @type response: C{str}
        @param response: scheme specific response string

        @type request: L{twisted.web.http.Request}
        @param request: The request being processed (from which the response
            was taken).

        @raise twisted.cred.error.LoginFailed: If the response is invalid.

        @rtype: L{twisted.cred.credentials.ICredentials} provider
        @return: The credentials represented by the given response.
        """



class IUsernameDigestHash(Interface):
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
