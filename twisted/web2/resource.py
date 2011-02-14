# -*- test-case-name: twisted.web2.test.test_server,twisted.web2.test.test_resource -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
I hold the lowest-level L{Resource} class and related mix-in classes.
"""

# System Imports
from zope.interface import implements

from twisted.web2 import iweb, http, server, responsecode

class RenderMixin(object):
    """
    Mix-in class for L{iweb.IResource} which provides a dispatch mechanism for
    handling HTTP methods.
    """
    def allowedMethods(self):
        """
        @return: A tuple of HTTP methods that are allowed to be invoked on this resource.
        """
        if not hasattr(self, "_allowed_methods"):
            self._allowed_methods = tuple([name[5:] for name in dir(self) if name.startswith('http_')])
        return self._allowed_methods

    def checkPreconditions(self, request):
        """
        Checks all preconditions imposed by this resource upon a request made
        against it.
        @param request: the request to process.
        @raise http.HTTPError: if any precondition fails.
        @return: C{None} or a deferred whose callback value is C{request}.
        """
        #
        # http.checkPreconditions() gets called by the server after every
        # GET or HEAD request.
        #
        # For other methods, we need to know to bail out before request
        # processing, especially for methods that modify server state (eg. PUT).
        # We also would like to do so even for methods that don't, if those
        # methods might be expensive to process.  We're assuming that GET and
        # HEAD are not expensive.
        #
        if request.method not in ("GET", "HEAD"):
            http.checkPreconditions(request)

        # Check per-method preconditions
        method = getattr(self, "preconditions_" + request.method, None)
        if method:
            return method(request)

    def renderHTTP(self, request):
        """
        See L{iweb.IResource.renderHTTP}.

        This implementation will dispatch the given C{request} to another method
        of C{self} named C{http_}METHOD, where METHOD is the HTTP method used by
        C{request} (eg. C{http_GET}, C{http_POST}, etc.).

        Generally, a subclass should implement those methods instead of
        overriding this one.

        C{http_*} methods are expected provide the same interface and return the
        same results as L{iweb.IResource}C{.renderHTTP} (and therefore this method).

        C{etag} and C{last-modified} are added to the response returned by the
        C{http_*} header, if known.

        If an appropriate C{http_*} method is not found, a
        L{responsecode.NOT_ALLOWED}-status response is returned, with an
        appropriate C{allow} header.

        @param request: the request to process.
        @return: an object adaptable to L{iweb.IResponse}.
        """
        method = getattr(self, "http_" + request.method, None)
        if not method:
            response = http.Response(responsecode.NOT_ALLOWED)
            response.headers.setHeader("allow", self.allowedMethods())
            return response

        d = self.checkPreconditions(request)
        if d is None:
            return method(request)
        else:
            return d.addCallback(lambda _: method(request))

    def http_OPTIONS(self, request):
        """
        Respond to a OPTIONS request.
        @param request: the request to process.
        @return: an object adaptable to L{iweb.IResponse}.
        """
        response = http.Response(responsecode.OK)
        response.headers.setHeader("allow", self.allowedMethods())
        return response

    def http_TRACE(self, request):
        """
        Respond to a TRACE request.
        @param request: the request to process.
        @return: an object adaptable to L{iweb.IResponse}.
        """
        return server.doTrace(request)

    def http_HEAD(self, request):
        """
        Respond to a HEAD request.
        @param request: the request to process.
        @return: an object adaptable to L{iweb.IResponse}.
        """
        return self.http_GET(request)

    def http_GET(self, request):
        """
        Respond to a GET request.

        This implementation validates that the request body is empty and then
        dispatches the given C{request} to L{render} and returns its result.

        @param request: the request to process.
        @return: an object adaptable to L{iweb.IResponse}.
        """
        if request.stream.length != 0:
            return responsecode.REQUEST_ENTITY_TOO_LARGE

        return self.render(request)

    def render(self, request):
        """
        Subclasses should implement this method to do page rendering.
        See L{http_GET}.
        @param request: the request to process.
        @return: an object adaptable to L{iweb.IResponse}.
        """
        raise NotImplementedError("Subclass must implement render method.")

class Resource(RenderMixin):
    """
    An L{iweb.IResource} implementation with some convenient mechanisms for
    locating children.
    """
    implements(iweb.IResource)

    addSlash = False

    def locateChild(self, request, segments):
        """
        Locates a child resource of this resource.
        @param request: the request to process.
        @param segments: a sequence of URL path segments.
        @return: a tuple of C{(child, segments)} containing the child
        of this resource which matches one or more of the given C{segments} in
        sequence, and a list of remaining segments.
        """
        w = getattr(self, 'child_%s' % (segments[0], ), None)

        if w:
            r = iweb.IResource(w, None)
            if r:
                return r, segments[1:]
            return w(request), segments[1:]

        factory = getattr(self, 'childFactory', None)
        if factory is not None:
            r = factory(request, segments[0])
            if r:
                return r, segments[1:]

        return None, []

    def child_(self, request):
        """
        This method locates a child with a trailing C{"/"} in the URL.
        @param request: the request to process.
        """
        if self.addSlash and len(request.postpath) == 1:
            return self
        return None

    def putChild(self, path, child):
        """
        Register a static child.

        This implementation registers children by assigning them to attributes
        with a C{child_} prefix.  C{resource.putChild("foo", child)} is
        therefore same as C{o.child_foo = child}.

        @param path: the name of the child to register.  You almost certainly
            don't want C{"/"} in C{path}. If you want to add a "directory"
            resource (e.g. C{/foo/}) specify C{path} as C{""}.
        @param child: an object adaptable to L{iweb.IResource}.
        """
        setattr(self, 'child_%s' % (path, ), child)

    def http_GET(self, request):
        if self.addSlash and request.prepath[-1] != '':
            # If this is a directory-ish resource...
            return http.RedirectResponse(request.unparseURL(path=request.path+'/'))

        return super(Resource, self).http_GET(request)


class PostableResource(Resource):
    """
    A L{Resource} capable of handling the POST request method.

    @cvar maxMem: maximum memory used during the parsing of the data.
    @type maxMem: C{int}
    @cvar maxFields: maximum number of form fields allowed.
    @type maxFields: C{int}
    @cvar maxSize: maximum size of the whole post allowed.
    @type maxSize: C{int}
    """
    maxMem = 100 * 1024
    maxFields = 1024
    maxSize = 10 * 1024 * 1024

    def http_POST(self, request):
        """
        Respond to a POST request.
        Reads and parses the incoming body data then calls L{render}.

        @param request: the request to process.
        @return: an object adaptable to L{iweb.IResponse}.
        """
        return server.parsePOSTData(request,
            self.maxMem, self.maxFields, self.maxSize
            ).addCallback(lambda res: self.render(request))


class LeafResource(RenderMixin):
    """
    A L{Resource} with no children.
    """
    implements(iweb.IResource)

    def locateChild(self, request, segments):
        return self, server.StopTraversal

class RedirectResource(LeafResource):
    """
    A L{LeafResource} which always performs a redirect.
    """
    implements(iweb.IResource)

    def __init__(self, *args, **kwargs):
        """
        Parameters are URL components and are the same as those for
        L{urlparse.urlunparse}.  URL components which are not specified will
        default to the corresponding component of the URL of the request being
        redirected.
        """
        self._args   = args
        self._kwargs = kwargs

    def renderHTTP(self, request):
        return http.RedirectResponse(request.unparseURL(*self._args, **self._kwargs))

class WrapperResource(object):
    """
    An L{iweb.IResource} implementation which wraps a L{RenderMixin} instance
    and provides a hook in which a subclass can implement logic that is called
    before request processing on the contained L{Resource}.
    """
    implements(iweb.IResource)

    def __init__(self, resource):
        self.resource=resource

    def hook(self, request):
        """
        Override this method in order to do something before passing control on
        to the wrapped resource's C{renderHTTP} and C{locateChild} methods.
        @return: None or a L{Deferred}.  If a deferred object is
            returned, it's value is ignored, but C{renderHTTP} and
            C{locateChild} are chained onto the deferred as callbacks.
        """
        raise NotImplementedError()

    def locateChild(self, request, segments):
        x = self.hook(request)
        if x is not None:
            return x.addCallback(lambda data: (self.resource, segments))
        return self.resource, segments

    def renderHTTP(self, request):
        x = self.hook(request)
        if x is not None:
            return x.addCallback(lambda data: self.resource)
        return self.resource


__all__ = ['RenderMixin', 'Resource', 'PostableResource', 'LeafResource', 'WrapperResource']
