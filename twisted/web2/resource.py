# -*- test-case-name: twisted.web.test.test_web -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I hold the lowest-level Resource class."""


# System Imports
from twisted.internet import defer
from twisted.python import roots, components, reflect
from zope.interface import implements

from twisted.web2 import iweb,http
from twisted.web2.iweb import IResource

class Resource:
    """I define a web-accessible resource.

    I serve 2 main purposes; one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    abstract directory structure for URL retrieval.
    """

    implements(iweb.IResource)
    
    server = None

    def __init__(self):
        """Initialize.
        """
        self.children = {}

    # Concrete HTTP interface

    def locateChild(self, request, segments):
        r = self.children.get(segments[0], None)
        
        if r:
            return r, segments[1:]

        w = getattr(self, 'child_%s'%segments[0], None)
        
        if w:
            if components.implements(w, iweb.IResource):
                return w, segments[1:]
            return w(request), segments[1:]

        r = self.getDynamicChild(segments[0], request)
        if r:
            return r, segments[1:]
     
        return error.NoResource(message = segments), []

    def getDynamicChild(self, path, request):
        return None

    def child_(self, request):
        """
            I'm how requests for '' get handled :)
        """
        return self

    def renderError(self, request):
        return None
        
    def putChild(self, path, child):
        """Register a static child.

        You almost certainly don't want '/' in your path. If you
        intended to have the root of a folder, e.g. /foo/, you want
        path to be ''.
        """
        self.children[path] = child
        child.server = self.server

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

    def render_HEAD(self, request):
        """Default handling of HEAD method.
        
        I just return self.render_GET(request). When method is HEAD,
        the framework will handle this correctly.
        """
        return self.render_GET(request)
components.backwardsCompatImplements(Resource)

class LeafResource(Resource):
    implements(iweb.IResource)

    def __init__(self):
        self.postpath = []

    def locateChild(self, request, segments):
        self.postpath = list(segments)
        return self, ()

components.backwardsCompatImplements(LeafResource)
#t.w imports
#This is ugly, I know, but since error.py directly access resource.Resource
#during import-time (it subclasses it), the Resource class must be defined
#by the time error is imported.
import error
