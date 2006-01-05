# -*- test-case-name: twisted.web2.test.test_server -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I hold the lowest-level Resource class."""


# System Imports
from twisted.python import components
from twisted.internet.defer import succeed, maybeDeferred
from zope.interface import implements

from twisted.web2 import iweb, http, server, responsecode

class Resource(object):
    """I define a web-accessible resource.

    I serve 2 main purposes; one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    abstract directory structure for URL retrieval.
    """

    implements(iweb.IResource)

    addSlash = False
    
    # Concrete HTTP interface

    def allowedMethods(self):
        """
        @return: A tuple of allowed methods.
        """
        if not hasattr(self, "_allowed_methods"):
            self._allowed_methods = tuple([name[5:] for name in dir(self) if name.startswith('http_')])
        return self._allowed_methods

    def exists(self):
        """
        @return: True if the resource exists on the server, False otherwise.
        """
        return None

    def etag(self):
        """
        @return: The current etag for the resource if available, None otherwise.
        """
        return None

    def lastModified(self):
        """
        @return: The last modified time of the resource if available, None otherwise.
        """
        return None

    def creationDate(self):
        """
        @return: The creation date of the resource if available, None otherwise.
        """
        return None

    def contentLength(self):
        """
        @return: The size in bytes of the resource if available, None otherwise.
        """
        return None

    def contentType(self):
        """
        @return: The MIME type of the resource if available, None otherwise.
        """
        return None

    def contentEncoding(self):
        """
        @return: The encoding of the resource if available, None otherwise.
        """
        return None

    def displayName(self):
        """
        @return: The display name of the resource if available, None otherwise.
        """
        return None

    def locateChild(self, req, segments):
        """Return a tuple of (child, segments) representing the Resource
        below this after consuming the segments which are not returned.
        """
        w = getattr(self, 'child_%s' % (segments[0], ), None)
        
        if w:
            r = iweb.IResource(w, None)
            if r:
                return r, segments[1:]
            return w(req), segments[1:]

        factory = getattr(self, 'childFactory', None)
        if factory is not None:
            r = factory(req, segments[0])
            if r:
                return r, segments[1:]
     
        return None, []
    
    def child_(self, req):
        """I'm how requests for '' (urls ending in /) get handled :)
        """
        if self.addSlash and len(req.postpath) == 1:
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
    
    def renderHTTP(self, req):
        """Render a given resource. See L{IResource}'s render method.

        I delegate to methods of self with the form 'http_METHOD'
        where METHOD is the HTTP that was used to make the
        request. Examples: http_GET, http_HEAD, http_POST, and
        so on. Generally you should implement those methods instead of
        overriding this one.

        http_METHOD methods are expected to return a byte string which
        will be the rendered page, or else a deferred that results
        in a byte string.
        """
        method = getattr(self, 'http_' + req.method, None)
        if not method:
            response = http.Response(responsecode.NOT_ALLOWED)
            response.headers.setHeader("allow", self.allowedMethods())
            return response

        def setHeaders(response):
            response = iweb.IResponse(response)

            # Content-* headers refer to the response content, not (necessarily) to
            # the resource content, so they depend on the request method, and
            # therefore can't be set here.
            for (header, value) in (
                ("etag", self.etag()),
                ("last-modified", self.lastModified()),
            ):
                if value is not None:
                    response.headers.setHeader(header, value)

            return response

        return maybeDeferred(method, req).addCallback(setHeaders)
            
    def http_HEAD(self, req):
        """By default http_HEAD just calls http_GET. The body is discarded
        when the result is being written.
        
        Override this if you want to handle it differently.
        """
        return self.http_GET(req)
    
    def http_GET(self, req):
        """Ensures there is no incoming body data, and calls render."""
        if self.addSlash and req.prepath[-1] != '':
            # If this is a directory-ish resource...
            return http.RedirectResponse(req.unparseURL(path=req.path+'/'))
            
        if req.stream.length != 0:
            return responsecode.REQUEST_ENTITY_TOO_LARGE

        def setHeaders(response):
            for (header, value) in (
                ("content-length", self.contentLength()),
                ("content-type", self.contentType()),
                ("content-encoding", self.contentEncoding()),
            ):
                if value is not None:
                    response.headers.setHeader(header, value)

            return response

        return maybeDeferred(self.render, req).addCallback(setHeaders)

    def http_OPTIONS(self, req):
        """Sends back OPTIONS response."""
        response = http.Response(responsecode.OK)
        response.headers.setHeader("allow", self.allowedMethods())
        return response

    def http_TRACE(self, req):
        return server.doTrace(req)
    
    def render(self, req):
        """Your class should implement this method to do default page rendering.
        """
        raise NotImplementedError("Subclass must implement render method.")

components.backwardsCompatImplements(Resource)

class PostableResource(Resource):
    def http_POST(self, req):
        """Reads and parses the incoming body data then calls render."""
        return server.parsePOSTData(req).addCallback(
            lambda res: self.render(req))
        
        
class LeafResource(Resource):
    def locateChild(self, request, segments):
        return self, server.StopTraversal

class WrapperResource(object):
    """A helper class for resources which just change some state
    before passing the request on to a contained resource."""
    implements(iweb.IResource)
    
    def __init__(self, res):
        self.res=res

    def hook(self, req):
        """Override this method in order to do something before
        passing control on to the wrapped resource. Must either return
        None or a Deferred which is waited upon, but whose result is
        ignored.
        """
        raise NotImplementedError
    
    def locateChild(self, req, segments):
        x = self.hook(req)
        if x is not None:
            return x.addCallback(lambda data: (self.res, segments))
        return self.res, segments

    def renderHTTP(self, req):
        x = self.hook(req)
        if x is not None:
            return x.addCallback(lambda data: self.res)
        return self.res
    

__all__ = ['Resource', 'LeafResource', 'PostableResource', 'WrapperResource']
