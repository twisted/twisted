
"""
Woven object collections.

THIS MODULE IS HIGHLY EXPERIMENTAL AND MAY BE DEPRECATED SOON.
"""

from __future__ import nested_scopes

__version__ = "$Revision: 1.7 $"[11:-2]

# System Imports
import time
import sys

# Twisted Imports

from twisted.internet.defer import Deferred

from twisted.web.resource import Resource, IResource
from twisted.web.static import redirectTo, addSlash, File, Data
from twisted.web.server import NOT_DONE_YET

from twisted.spread.refpath import PathReferenceAcquisitionContext

from twisted.python.reflect import qual
from twisted.python import components

# Sibling Imports
from twisted.web.woven.view import View

class _ChildJuggler(Resource):
    isLeaf = 1
    def __init__(self, d):
        Resource.__init__(self)
        self.d = d

    def render(self, request):
        # TODO: getChild stuffs
        self.d.addCallback(self._cbChild, request).addErrback(
            self._ebChild,request)
        return NOT_DONE_YET

    def _cbChild(self, child, request):
        request.render(child)
        return child

    def _ebChild(self, reason, request):
        request.processingFailed(reason)
        return reason


class ModelLoader(Resource):
    """Resource for loading models.  (see loadModel)
    """
    def __init__(self, parent, templateFile=None):
        Resource.__init__(self)
        self.parent = parent
        self._templateFile = templateFile

    def getChild(self, path, request):
        d = self.loadModel(path, request)
        templateFile = (self.templateFile or self.__class__.__name__+'.html')
        d.addCallback(
            lambda result: self.parent.makeView(self.modelClass(result),
                                                self.templateFile))
        return _ChildJuggler(d)

    def loadModelNow(self, path, request):
        """Override this rather than loadModel if your model-loading is
        synchronous.
        """
        raise NotImplementedError("%s.loadModelNow" % (reflect.qual(self.__class__)))

    def loadModel(self, path, request):
        """Load a model, for the given path and request.

        @rtype: L{Deferred}
        """
        from twisted.internet.defer import execute
        return execute(self.loadModelNow, path, request)


class Tapestry(Resource):
    """
    I am a top-level aggregation of Woven objects: a full `site' or
    `application'.
    """
    viewFactory = View
    def __init__(self, templateDirectory, viewFactory=None):
        """
        Create a tapestry with a specified template directory.
        """
        Resource.__init__(self)
        self.templateDirectory = templateDirectory
        if viewFactory is not None:
            self.viewFactory = viewFactory

    def makeView(self, model, name):
        v = self.viewFactory(model, name)
        v.templateDirectory = self.templateDirectory
        v.importViewLibrary(self)
        return v

    def getSubview(self, request, node, model, viewName):
        mod = sys.modules[self.__class__.__module__]
        # print "I'm getting a subview", mod, viewName
        # try just the name
        vm = getattr(mod, viewName, None)
        if vm:
            return vm(model)
        # try the name + a V
        vn2 = "V"+viewName.capitalize()
        vm = getattr(mod, vn2, None)
        if vm:
            return vm(model)

    def render(self, request):
        return redirectTo(addSlash(request), request)

    def getChild(self, path, request):
        if isinstance(request, PathReferenceAcquisitionContext):
            # temporary hack to get around acquisition, since we rather
            # explicitly don't want it here.
            return None
        if path == '': path = 'index'
        cm = getattr(self, "wchild_"+path, None)
        if cm:
            p = cm(request)
            if isinstance(p, Deferred):
                return _ChildJuggler(p)
            adapter = components.getAdapter(p, IResource, None)
            if adapter is not None:
                return adapter
        return Resource.getChild(self, path, request)
