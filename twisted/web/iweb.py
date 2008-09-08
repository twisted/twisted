# -*- test-case-name: twisted.web.test -*-
# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interface definitions for L{twisted.web}.
"""

from zope.interface import Interface, Attribute

from twisted.internet.interfaces import IConsumer


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



class IHTTPRequest(Interface):
    """
    @ivar uri: The full C{Request-URI} (rfc 2616) that is being requested,
        including any query part.
    @ivar path: The C{Request-URI} minus any query part.
    """

    def setURI(path):
        """
        Set the URI that this request is handling. This must set the L{uri} and
        L{path} attributes of this request as per their specification.
        """



class IHTTPResponse(Interface):
    """
    The basic definition of an HTTP response.

    This is the interface to an HTTP response object as seen by the HTTP
    protocol. It is not concerned with constructing and configuring an HTTP
    response, it is only concerned with getting the data for the
    response. Providers of this interface should provide other methods for
    specifying the data.
    """

    def getResponseCode():
        """
        @return: the previously-specified HTTP response code.
        @rtype: Two tuple of code and message.
        """


    def getHeaders():
        """
        Return all response headers. The header names must all be lower-case.

        @rtype: C{dict} of header name to value.
        """


    def writeBody(receiver):
        """
        Send data to the given C{receiver}.

        This method can optionally call
        L{IHTTPResponseReceiver.registerProducer} on the given C{receiver} if
        it cares about writability notification.

        This method MUST cause L{IHTTPResponseReceiver.finishResponse} to be
        called.

        @param receiver: The object that when written to will send data to the
            HTTP client.
        @type receiver: L{IHTTPResponseReceiver}
        """



class IHTTPChannel(Interface):
    """
    The HTTP protocol.

    """

    def setHTTPRequestReceiver(receiver):
        """
        @param receiver: The request receiver that will be notified when
            requests are made.
        @type receiver: L{IHTTPRequestReceiver}.
        """



class IHTTPResponseReceiver(IConsumer):
    """
    The object that HTTP response data gets sent to.

    Notably, this interface extends IConsumer.
    """

    def finishResponse():
        """
        Finish the current response. No more data should be written to it for
        the current response.
        """



class IHTTPRequestReceiver(Interface):

    def requestReceived(request):
        """
        Process a request and return an L{IHTTPResponse}.

        @param request: The request to respond to
        @type request: L{IHTTPRequest}


        @return: The deferred HTTP response object that will be asked to send
            its response. By the time the Deferred fires, the response code and
            headers must be prepared. See L{IHTTPResponse}.

        @rtype: L{Deferred} of L{IHTTPResponse}
        """
