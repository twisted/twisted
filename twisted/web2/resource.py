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
    
    server = None

    # Concrete HTTP interface

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
        return self
        
    def putChild(self, path, child):
        """Register a static child.

        You almost certainly don't want '/' in your path. If you
        intended to have the root of a folder, e.g. /foo/, you want
        path to be ''.
        """
        setattr(self, 'child_%s' % (path, ), child)

    def render(self, request):
        """Render a given resource. See L{IResource}'s render method.

        I delegate to methods of self with the form 'render_METHOD'
        where METHOD is the HTTP that was used to make the
        request. Examples: render_GET, render_HEAD, render_POST, and
        so on. Generally you should implement those methods instead of
        overriding this one.

        render_METHOD methods are expected to return a string which
        will be the rendered page, unless the return value is
        twisted.web.server.NOT_DONE_YET, in which case it is this
        class's responsibility to write the results to
        request.write(data), then call request.finish().

        Old code that overrides render() directly is likewise expected
        to return a string or NOT_DONE_YET.
        """
        m = getattr(self, 'render_' + request.method, None)
        if not m:
            from twisted.web.server import UnsupportedMethod
            raise UnsupportedMethod(getattr(self, 'allowedMethods', ()))
        return m(request)

    render_HEAD = property(lambda self: getattr(self, 'render_GET', None), doc="""\
By default render_HEAD just renders the whole body (by calling render_GET),
calculates the body size, and eats the body (does not send it to the client).

Override this if you want to handle it differently.
""")
 
components.backwardsCompatImplements(Resource)

class LeafResource(Resource):
    implements(iweb.IResource)

    def __init__(self):
        self.postpath = []

    def locateChild(self, request, segments):
        self.postpath = list(segments)
        return self, ()

components.backwardsCompatImplements(LeafResource)
