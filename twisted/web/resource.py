# -*- test-case-name: twisted.web.test.test_web -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I hold the lowest-level Resource class."""


# System Imports
from twisted.internet import defer
from twisted.python import roots, reflect
from zope.interface import Attribute, implements, Interface

class IResource(Interface):
    """A web resource."""

    isLeaf = Attribute(\
"""Signal if this IResource implementor is a "leaf node" or not. If True,
getChildWithDefault will not be called on this Resource.""")

    def getChildWithDefault(name, request):
        """Return a child with the given name for the given request.
        This is the external interface used by the Resource publishing
        machinery. If implementing IResource without subclassing
        Resource, it must be provided. However, if subclassing Resource,
        getChild overridden instead.
        """

    def putChild(path, child):
        """Put a child IResource implementor at the given path.
        """

    def render(request):
        """Render a request. This is called on the leaf resource for
        a request. Render must return either a string, which will
        be sent to the browser as the HTML for the request, or
        server.NOT_DONE_YET. If NOT_DONE_YET is returned,
        at some point later (in a Deferred callback, usually)
        call request.write("<html>") to write data to the request,
        and request.finish() to send the data to the browser.
        """


def getChildForRequest(resource, request):
    """Traverse resource tree to find who will handle the request."""
    while request.postpath and not resource.isLeaf:
        pathElement = request.postpath.pop(0)
        request.prepath.append(pathElement)
        resource = resource.getChildWithDefault(pathElement, request)
    return resource


class Resource:
    """I define a web-accessible resource.

    I serve 2 main purposes; one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    abstract directory structure for URL retrieval.
    """

    implements(IResource)
    
    entityType = IResource

    server = None

    def __init__(self):
        """Initialize.
        """
        self.children = {}

    isLeaf = 0

    ### Abstract Collection Interface

    def listStaticNames(self):
        return self.children.keys()

    def listStaticEntities(self):
        return self.children.items()

    def listNames(self):
        return self.listStaticNames() + self.listDynamicNames()

    def listEntities(self):
        return self.listStaticEntities() + self.listDynamicEntities()

    def listDynamicNames(self):
        return []

    def listDynamicEntities(self, request=None):
        return []

    def getStaticEntity(self, name):
        return self.children.get(name)

    def getDynamicEntity(self, name, request):
        if not self.children.has_key(name):
            return self.getChild(name, request)
        else:
            return None

    def delEntity(self, name):
        del self.children[name]

    def reallyPutEntity(self, name, entity):
        self.children[name] = entity

    # Concrete HTTP interface

    def getChild(self, path, request):
        """Retrieve a 'child' resource from me.

        Implement this to create dynamic resource generation -- resources which
        are always available may be registered with self.putChild().

        This will not be called if the class-level variable 'isLeaf' is set in
        your subclass; instead, the 'postpath' attribute of the request will be
        left as a list of the remaining path elements.

        For example, the URL /foo/bar/baz will normally be::

          | site.resource.getChild('foo').getChild('bar').getChild('baz').

        However, if the resource returned by 'bar' has isLeaf set to true, then
        the getChild call will never be made on it.

        @param path: a string, describing the child

        @param request: a twisted.web.server.Request specifying meta-information
                        about the request that is being made for this child.
        """
        return error.NoResource("No such child resource.")

    def getChildWithDefault(self, path, request):
        """Retrieve a static or dynamically generated child resource from me.

        First checks if a resource was added manually by putChild, and then
        call getChild to check for dynamic resources. Only override if you want
        to affect behaviour of all child lookups, rather than just dynamic
        ones.

        This will check to see if I have a pre-registered child resource of the
        given name, and call getChild if I do not.
        """
        if self.children.has_key(path):
            return self.children[path]

        return self.getChild(path, request)

    def getChildForRequest(self, request):
        import warnings
        warnings.warn("Please use module level getChildForRequest.", DeprecationWarning, 2)
        return getChildForRequest(self, request)
    
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


#t.w imports
#This is ugly, I know, but since error.py directly access resource.Resource
#during import-time (it subclasses it), the Resource class must be defined
#by the time error is imported.
import error
