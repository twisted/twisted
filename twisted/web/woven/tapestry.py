
"""
Woven object collections.

THIS MODULE IS HIGHLY EXPERIMENTAL AND MAY BE DEPRECATED SOON.
"""

from __future__ import nested_scopes

__version__ = "$Revision: 1.13 $"[11:-2]


import warnings
warnings.warn("The tapestry module is deprecated. Use page instead.", DeprecationWarning, 1)

# System Imports
import sys
import os

# Twisted Imports

from twisted.internet.defer import Deferred

from twisted.web.resource import Resource, IResource
from twisted.web.static import redirectTo, addSlash, File, Data
from twisted.web.server import NOT_DONE_YET
from twisted.web import util

from twisted.python.reflect import qual

# Sibling Imports
from twisted.web.woven.view import View

_ChildJuggler = util.DeferredResource

class ModelLoader(Resource):
    """Resource for loading models.  (see loadModel)
    """
    def __init__(self, parent, templateFile=None):
        Resource.__init__(self)
        self.parent = parent
        self.templateFile = templateFile

    def modelClass(self, other):
        return other

    def getChild(self, path, request):
        d = self.loadModel(path, request)
        templateFile = (self.templateFile or self.__class__.__name__+'.html')
        d.addCallback(
            lambda result: self.parent.makeView(self.modelClass(result),
                                                templateFile, 1))
        return util.DeferredResource(d)

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


from twisted.web import microdom
from twisted.web import domhelpers

class TapestryView(View):
    tapestry = None
    parentCount = 0
    def lookupTemplate(self, request):
        fullFile = os.path.join(self.templateDirectory, self.templateFile)
        document = microdom.parse(open(fullFile))
        if self.tapestry:
            return self.tapestry.templateMutate(document, self.parentCount)
        return document

class Tapestry(Resource):
    """
    I am a top-level aggregation of Woven objects: a full `site' or
    `application'.
    """
    viewFactory = TapestryView
    def __init__(self, templateDirectory, viewFactory=None, metaTemplate=None):
        """
        Create a tapestry with a specified template directory.
        """
        Resource.__init__(self)
        self.templateDirectory = templateDirectory
        if viewFactory is not None:
            self.viewFactory = viewFactory
        if metaTemplate:
            self.metaTemplate = microdom.parse(open(
                os.path.join(templateDirectory, metaTemplate)))
        else:
            self.metaTemplate = None

    def templateMutate(self, document, parentCount=0):
        if self.metaTemplate:
            newDoc = self.metaTemplate.cloneNode(1)
            if parentCount:
                dotdot = parentCount * '../'
                for ddname in 'href', 'src', 'action':
                    for node in domhelpers.findElementsWithAttribute(newDoc, ddname):
                        node.setAttribute(ddname, dotdot + node.getAttribute(ddname))
            ttl = domhelpers.findNodesNamed(newDoc, "title")[0]
            ttl2 = domhelpers.findNodesNamed(document, "title")[0]
            ttl.childNodes[:] = []
            for n in ttl2.childNodes:
                ttl.appendChild(n)
            body = domhelpers.findElementsWithAttribute(newDoc, "class", "__BODY__")[0]
            body2 = domhelpers.findNodesNamed(document, "body")[0]
            ndx = body.parentNode.childNodes.index(body)
            body.parentNode.childNodes[ndx:ndx+1] = body2.childNodes
            for n in body2.childNodes:
                n.parentNode = body.parentNode
            f = open("garbage.html", "wb")
            f.write(newDoc.toprettyxml())
            return newDoc
        return document

    def makeView(self, model, name, parentCount=0):
        v = self.viewFactory(model, name)
        v.parentCount = parentCount
        v.templateDirectory = self.templateDirectory
        v.tapestry = self
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

        vm = getattr(self, 'wvfactory_'+viewName, None)
        if vm:
            return vm(request, node, model)

    def render(self, request):
        return redirectTo(addSlash(request), request)

    def getChild(self, path, request):
        if path == '': path = 'index'
        path = path.replace(".","_")
        cm = getattr(self, "wchild_"+path, None)
        if cm:
            p = cm(request)
            if isinstance(p, Deferred):
                return util.DeferredResource(p)
            adapter = IResource(p, None)
            if adapter is not None:
                return adapter
        # maybe we want direct support for ModelLoader?
        # cl = getattr(self, "wload_"+path, None) #???
        return Resource.getChild(self, path, request)
