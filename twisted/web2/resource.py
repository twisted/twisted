# -*- test-case-name: twisted.web2.test.test_server -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
I hold the lowest-level L{Resource} class and related mix-in classes.
"""

# System Imports
from twisted.python import components
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
        """
        http.checkPreconditions(request)

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
        """
        method = getattr(self, 'http_' + request.method, None)
        if not method:
            response = http.Response(responsecode.NOT_ALLOWED)
            response.headers.setHeader("allow", self.allowedMethods())
            return response

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
            self.checkPreconditions(request)

        return method(request)

    def http_OPTIONS(self, request):
        """
        Respond to a OPTIONS request.
        """
        response = http.Response(responsecode.OK)
        response.headers.setHeader("allow", self.allowedMethods())
        return response

    def http_TRACE(self, request):
        """
        Respond to a TRACE request.
        """
        return server.doTrace(request)

    def http_HEAD(self, request):
        """
        Respond to a HEAD request.
        """
        return self.http_GET(request)
    
    def http_GET(self, request):
        """
        Respond to a GET request.

        Dispatches the given C{request} to C{self.render} and returns its
        result.
        """
        if request.stream.length != 0:
            return responsecode.REQUEST_ENTITY_TOO_LARGE

        return self.render(request)

    def render(self, request):
        """
        Subclasses should implement this method to do page rendering.
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
        """Return a tuple of (child, segments) representing the Resource
        below this after consuming the segments which are not returned.
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
        """I'm how requests for '' (urls ending in /) get handled :)
        """
        if self.addSlash and len(request.postpath) == 1:
            return self
        return None
        
    def putChild(self, path, child):
        """Register a static child. "o.putChild('foo', something)" is the
        same as "o.child_foo = something".
        
        You almost certainly don't want '/' in your path. If you
        intended to have the root of a folder, e.g. /foo/, you want
        path to be ''.
        """
        setattr(self, 'child_%s' % (path, ), child)
    
    def http_GET(self, request):
        """Ensures there is no incoming body data, and calls render."""
        if self.addSlash and request.prepath[-1] != '':
            # If this is a directory-ish resource...
            return http.RedirectResponse(request.unparseURL(path=request.path+'/'))
            
        return super(Resource, self).http_GET(request)

components.backwardsCompatImplements(Resource)

class PostableResource(Resource):
    def http_POST(self, request):
        """Reads and parses the incoming body data then calls render."""
        return server.parsePOSTData(request).addCallback(
            lambda res: self.render(request))
        
class LeafResource(RenderMixin):
    implements(iweb.IResource)

    def locateChild(self, request, segments):
        return self, ()

class WrapperResource(object):
    """A helper class for resources which just change some state
    before passing the request on to a contained resource."""
    implements(iweb.IResource)
    
    def __init__(self, res):
        self.res=res

    def hook(self, request):
        """Override this method in order to do something before
        passing control on to the wrapped resource. Must either return
        None or a Deferred which is waited upon, but whose result is
        ignored.
        """
        raise NotImplementedError
    
    def locateChild(self, request, segments):
        x = self.hook(request)
        if x is not None:
            return x.addCallback(lambda data: (self.res, segments))
        return self.res, segments

    def renderHTTP(self, request):
        x = self.hook(request)
        if x is not None:
            return x.addCallback(lambda data: self.res)
        return self.res
    

__all__ = ['RenderMixin', 'Resource', 'PostableResource', 'LeafResource', 'WrapperResource']
