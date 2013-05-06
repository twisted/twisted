# -*- test-case-name: twisted.web.test.test_web -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of a low-level Resource class and related dependencies.
"""

__metaclass__ = type

from zope.interface import Interface
from twisted.web.iweb import IBodyProducer, UNKNOWN_LENGTH
from twisted.web.http_headers import Headers
from twisted.web.http import OK



class IResource(Interface):
    """
    An HTTP resource.

    I serve 2 main purposes: one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    mechanism for mapping URLs to content.
    """

    def locateChild(req, segments):
        """
        Locate another object which can be adapted to IResource.

        @return: A 2-tuple of (resource, remaining-path-segments), or a
            C{Deferred} which will fire the above.  Causes the object publishing
            machinery to continue on with specified resource and segments,
            calling the appropriate method on the specified resource.
        """

    def render(req):
        """
        Return a L{Response} instance, or a C{Deferred} which will fire with a
        L{Response}. This response will be written to the web browser which
        initiated the request.
        """


class Response:
    """
    All the information needed for a response to an HTTP request.

    @ivar code: The HTTP response code.
    @ivar headers: A L{Headers} instance.
    @ivar body: A {IBodyProducer}, a C{str} or C{None} if there is no
        body. Should be set using L{Response.setBody} or via the initializer.
    """

    def __init__(self, code=OK, headers=None, body=None):
        self.code = code
        if headers is None:
            headers = Headers()
        else:
            headers = headers.copy()
        self.headers = headers
        if body is None:
            self.body = None
        else:
            self.setBody(body)


    def setBody(self, body):
        """
        Set the body for the response.

        The body can only be set once. If the body has a length, a
        content-length header will be added.

        @param body: A C{str} or C{IBodyProducer}.
        """
        if isinstance(body, str):
            length = len(body)
        else:
            length = body.length
        if length != UNKNOWN_LENGTH:
            self.headers.addRawHeader("content-length", str(length))
        self.body = body
