# -*- test-case-name: twisted.web.test.test_web -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I hold the lowest-level Resource class."""


# System Imports
from twisted.python import components
from zope.interface import implements

from twisted.web2 import iweb

class Resource(object):
    """I define a web-accessible resource.

    I serve 2 main purposes; one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    abstract directory structure for URL retrieval.
    """

    implements(iweb.IResource)

    addSlash = False
    
    # Concrete HTTP interface

    def locateChild(self, ctx, segments):
        """Return a tuple of (child, segments) representing the Resource
        below this after consuming the segments which are not returned.
        """
        w = getattr(self, 'child_%s' % (segments[0], ), None)
        
        if w:
            r = iweb.IResource(w, None)
            if r:
                return r, segments[1:]
            return w(ctx), segments[1:]

        factory = getattr(self, 'childFactory', None)
        if factory is not None:
            r = factory(ctx, segments[0])
            if r:
                return r, segments[1:]
     
        return None, []
    
    def child_(self, ctx):
        """I'm how requests for '' (urls ending in /) get handled :)
        """
        if self.addSlash and iweb.ICurrentSegments(ctx)[-1] != '':
            request.redirect(request.URLPath().child(''))
            return ''
        return self
        
    def putChild(self, path, child):
        """Register a static child. "o.putChild('foo', something)" is the
        same as "o.child_foo = something".
        
        You almost certainly don't want '/' in your path. If you
        intended to have the root of a folder, e.g. /foo/, you want
        path to be ''.
        """
        setattr(self, 'child_%s' % (path, ), child)

    
    def renderHTTP(self, context):
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
        m = getattr(self, 'http_' + iweb.IRequest(ctx).method, None)
        if not m:
            raise error.MethodNotAllowed(getattr(self, 'allowedMethods', ()))
        return m(ctx)

    def http_HEAD(self, ctx):
        """By default http_HEAD just calls http_GET. The body is discarded
        when the result is being written.
        
        Override this if you want to handle it differently.
        """
        return self.http_GET(ctx)
    
    def http_GET(self, ctx):
        """Ensures there is no incoming body data, and calls render."""
        self.rejectData()
        return self.render(self, ctx)

    def render(self, ctx):
        """Your class should implement this method to do default page rendering.
        """
        raise NotImplementedError("Subclass must implement render method.")
    
class PostableResource(Resource):
    def http_POST(self, ctx):
        """Reads and parses the incoming body data then calls render."""
        request = iweb.IRequest(ctx)
        while repeatALot:
            request.stream.read()
            FIXME
        
        return self.render(self, ctx)
    
components.backwardsCompatImplements(Resource)

class LeafResource(Resource):
    implements(iweb.IResource)

    def __init__(self):
        self.postpath = []

    def locateChild(self, request, segments):
        self.postpath = list(segments)
        return self, ()

components.backwardsCompatImplements(LeafResource)
