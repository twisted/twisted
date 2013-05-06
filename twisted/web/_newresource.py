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


# A special object indicating the index part of a URL path. E.g. /foo/bar is
# the path [u"foo", u"bar"], /foo/bar/ is [u"foo", u"bar", INDEX] and //foo/
# is [INDEX, u"FOO"]:
INDEX = object()


class Path:
    """
    A URL path, a series of segments.

    @ivar segmentName: The current segment's name, either a C{unicode} string
        or the C{INDEX} constant.

    @ivar _segments: C{tuple} of C{unicode} strings or C{INDEX} object.
    """

    def __init__(self, segments):
        pass


    def child(self):
        """
        Return the next child L{Path}, i.e. without the current top-level path
        segment.

        C{None} will be returned if no segments remain.
        """


    def traverse(self, resource):
        """
        Return an object comprehensible to the resource-traversal mechanism,
        indicating that this path will be traversed by the given resource.
        """



class _TraversalStep(tuple):
    """
    A step in the traversal history for a path.

    This will be created by L{Path.traverse}.
    """

    def  __new__(path, resource):
        tuple.__new__(_TraversalStep, path, resource)



class IResource(Interface):
    """
    An HTTP resource.

    I serve 2 main purposes: one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    mechanism for mapping URLs to content.
    """

    def traverseChild(request, path):
        """
        Locate another object which can handle the remaining path segments.

        If this method will consume one or more path segments, return the
        result of calling C{traverse} on the child path. C{traverse} should be
        called with a L{IResource} provider that will handle the remaining
        segments. You can also return a C{Deferred} that fires with the result
        of C{traverse}.

        Here's an example that consumes /YYYY/MM/DD URLs::

            def traverseChild(self, request, path):
                year = int(path.segmentName)
                monthPath = path.child()
                month = int(monthPath.segmentName)
                dayPath = monthPath.child()
                day = int(dayPath.segmentName)
                return dayPath.traverse(DateResource(year, month, day))

        To provide a resource that will handle the full given path, just
        return the result of calling C{traverse} on the C{path} passed in to
        this method.

        For example, here's an implementation that returns different resources
        depending on some sort of authentication mechanism::

            def traverseChild(self, request, path):
                if isAuthenticated(request):
                    resource = SecretResource()
                else:
                    resource = PermissionDenied()
                return path.traverse(resource)
        """


    def renderHTTP(request, traversalHistory):
        """
        @param traversalHistory: A list of (path, resource) tuples.

        Return a L{Response} instance, or a C{Deferred} which will fire with a
        L{Response}. This response will be written to the web browser which
        initiated the request.
        """


class Traversal:
    """
    Traverse a path, finding the leaf L{IResource} that will render the
    corresponding web entity.

    @ivar history: a C{list} of (L{Path}, L{IResource}) tuples, the traversal
        history.
    """

    def __init__(self, path, rootResource):
        pass


    def traverse(self):
        """
        Return a C{Deferred} that fires with a L{IResource} that can render
        the entity indicated by the path.
        """



class Response:
    """
    All the information needed for a response to an HTTP request.

    @ivar code: The HTTP response code.
    @ivar headers: A L{Headers} instance.
    @ivar body: A {IBodyProducer}, a C{str} or C{None} if there is no
        body. Should be set using L{Response.setBody} or via the initializer.
    """

    body = None

    def __init__(self, code=OK, headers=None, body=None):
        self.code = code
        if headers is None:
            headers = Headers()
        else:
            headers = headers.copy()
        self.headers = headers
        if body is not None:
            self.setBody(body)


    def setBody(self, body):
        """
        Set the body for the response; this can only be done once.

        @param body: A C{str} or C{IBodyProducer}.
        """
        if self.body is not None:
            raise RuntimeError("Can't set body twice.")
        self.body = body
