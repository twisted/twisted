# -*- test-case-name: twisted.web.test.test_newresource -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of a low-level Resource class and related dependencies.
"""

__metaclass__ = type

from zope.interface import Interface
from twisted.web.iweb import IBodyProducer, UNKNOWN_LENGTH
from twisted.python.reflect import fullyQualifiedName
from twisted.web.http_headers import Headers
from twisted.web.http import OK


# A more meaningful name for the index part of a URL path. E.g. /foo/bar is
# the path [u"foo", u"bar"], /foo/bar/ is [u"foo", u"bar", INDEX] and //foo/
# is [INDEX, u"FOO"]:
INDEX = u""


class Path:
    """
    A URL path, a series of segments.

    @ivar segments: C{tuple} of C{unicode} strings or C{INDEX} object.
    """

    def __init__(self, segments):
        self.segments = segments


    @classmethod
    def fromString(klass, path, encoding="UTF-8"):
        """
        Create a L{Path} from its byte representation.
        """
        # XXX url decode
        return klass(tuple([p.decode(encoding) for p in path.split("/")[1:]]))


    @classmethod
    def leaf(klass):
        """
        Return a L{Path} that has no more segments left.
        """
        return klass(())


    def child(self):
        """
        Return a tuple (segment, child L{Path}), i.e. consume the current
        top-level path segment.

        @raises Something: If this is a leaf path.
        """
        segments, child = self.descend(1)
        segment = segments[0]
        return segment, child


    def descend(self, depth):
        """
        Return a tuple of (segments, child L{Path}) which consumes C{depth}
        segments of the path.

        @raises Something: If depth is too high.
        """
        if depth > len(self.segments):
            raise ValueError("Cannot descend %d segments, Path only contains "
                "%d: %r" %(depth, len(self.segments), self.segments))
        return self.segments[0:depth], self.__class__(self.segments[depth:])


    def traverseUsing(self, resource):
        """
        Return an object comprehensible to the resource-traversal mechanism,
        indicating that this path will be traversed by the given resource.

        @param resource: a L{IResource} provider, or a C{Deferred} that will
            fire with one.
        """
        return _TraversalStep(self, resource)


    def __eq__(self, other):
        return self.segments == other.segments


    def __repr__(self):
        return "<%s %r>" % (fullyQualifiedName(self.__class__), self.segments)



class _TraversalStep(tuple):
    """
    A step in the traversal history for a path.

    This will be created by L{Path.traverse}.
    """

    def  __new__(klass, path, resource):
        return tuple.__new__(klass, (path, resource))



class IResource(Interface):
    """
    An HTTP resource.

    I serve 2 main purposes: one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    mechanism for mapping URLs to content.
    """

    def traverse(request, path):
        """
        Locate another object which can handle the remaining path segments.

        If this method will consume one or more path segments, return the
        result of calling C{traverseUsing} on the child path. C{traverseUsing}
        should be called with a L{IResource} provider that will handle the
        remaining segments. You can also call C{traverseUsing} with a
        C{Deferred} that fires with a L{IResource}.

        For example, this resource consumes only one path segment::

            def traverse(self, request, path):
                segmentName, child = path.child()
                return child.traverseUsing(ChildResource(segmentName))

        Here's an example that consumes /YYYY/MM/DD URLs::

            def traverse(self, request, path):
                (year, month, day), child = path.descend(3)
                return child.traverseUsing(DateResource(year, month, day))

        To provide a resource that will handle the full given path, just
        return the result of calling C{traverseUsing} on the C{path} passed in
        to this method. For example, here's an implementation that returns
        different resources depending on asynchronous authentication
        mechanism::

            def traverse(self, request, path):
                d = authenticate(request)
                d.addCallbacks(AuthenticatedResource, PermissionDenied)
                return path.traverseUsing(d)

        Finally, here's an example of consuming the whole path, regardless of
        its length::

            def traverse(self, request, path):
                return path.leaf().traverseUsing(
                    CustomURLDispatcher(path.segments))
        """


    def renderHTTP(request, traversalHistory):
        """
        @param traversalHistory: A list of (path, resource) tuples.

        Return a L{Response} instance, or a C{Deferred} which will fire with a
        L{Response}. This response will be written to the HTTP client which
        initiated the request.
        """



def traverse(request, path, rootResource):
    """
    Traverse a path, finding the leaf L{IResource} that will render the
    corresponding web entity.

    @return: A C{Deferred} that fires with a C{list} of (L{Path},
        L{IResource}) tuples, the traversal history. The final L{IResource} is
        the one that can render the given HTTP request.
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
