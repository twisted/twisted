
# Twisted, the Framework of Your Internet
# Copyright (C) 2000-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from __future__ import nested_scopes

# Sibling imports
import interfaces
import template
import utils
import model

# Twisted imports
from twisted.internet import defer
from twisted.python import components
from twisted.python import log
from twisted.web import resource, microdom, server


import warnings


NO_DATA_YET = 2


def viewFactory(viewClass):
    return lambda request, node, model: viewClass(model)

def viewMethod(viewClass):
    return lambda self, request, node, model: viewClass(model)


class IWovenLivePage(server.Session):
    def getCurrentPage():
        """Return the current page object contained in this session.
        """

    def setCurrentPage(page):
        """Set the current page object contained in this session.
        """

class WovenLivePage:
    currentPage = None
    def getCurrentPage(self):
        """Return the current page object contained in this session.
        """
        return self.currentPage

    def setCurrentPage(self, page):
        """Set the current page object contained in this session.
        """
        self.currentPage = page


class View(template.DOMTemplate):

    __implements__ = (template.DOMTemplate.__implements__, interfaces.IView)

    wantsAllNotifications = 1

    def __init__(self, m, templateFile=None):
        """
        A view must be told what its model is, and may be told what its
        controller is, but can also look up its controller if none specified.
        """
        self.model = self.mainModel = model.adaptToIModel(m, None, None)
        self.controller = self.controllerFactory(self.model)
        self.modelStack = [self.model]
        self.viewStack = [self, widgets]
        self.subviews = {}
        self.currentId = 0
        self.controllerStack = [self.controller, input]
        template.DOMTemplate.__init__(self, self.model, templateFile)

    def getTopOfModelStack(self):
        for x in self.modelStack:
            if x is not None:
                return x
        
    def modelChanged(self, changed):
        """
        Dispatch changed messages to any update_* methods which
        may have been defined, then pass the update notification on
        to the controller.
        """
        for name in changed.keys():
            handler = getattr(self, 'update_' + name, None)
            if handler:
                apply(handler, (changed[name],))

    def controllerFactory(self, model):
        """
        Hook for subclasses to customize the controller that is associated
        with the model associated with this view.
        """
        # TODO: Decide what to do as a default Controller
        # if you don't need to use one...
        # Something that ignores all messages?
        controller = components.getAdapter(model, interfaces.IController, None)
        if controller:
            controller.setView(self)
        return controller
        
    def setController(self, controller):
        self.controller = controller

    def setNode(self, node):
        self.node = node
    
    def setSubmodel(self, name):
        self.submodel = name
    
    def getNodeModel(self, request, node, submodel):
        """
        Get the model object associated with this node. If this node has a
        model= attribute, call getSubmodel on the current model object.
        If not, return the top of the model stack.
        """
        if submodel:
            for parent in self.modelStack:
                if parent is None: continue
                f = getattr(parent, "wmfactory_%s" % submodel, None)
                if f is not None: break
            if f:
                m = f(request, node)
            elif submodel == '.':
                m = self.getTopOfModelStack()
            else:
                for x in self.modelStack:
                    if x is None:
                        continue
                    m = x.lookupSubmodel(submodel)
                    if m is not None:
                        break
                else:
                    warnings.warn("POTENTIAL ERROR: Node had a model=%s "
                                  "attribute, but the submodel did not "
                                  "exist." % (submodel, ))
                    m = self.getTopOfModelStack()
        else:
            m = None
        self.modelStack.insert(0, m)
        if m:
            if parent is not m:
                m.parent = parent
            if not getattr(m, 'name', None):
                m.name = submodel
        if submodel:
            return self.getTopOfModelStack()
        return None

    def getNodeController(self, request, node, submodel, model):
        """
        Get a controller object to handle this node. If the node has no
        controller= attribute, first check to see if there is an IController
        adapter for our model.
        """
        controllerName = node.getAttribute('controller')
        
        if model is None:
            model = self.getTopOfModelStack()

        # Look up a controller factory.
        if controllerName:
            if not node.hasAttribute('name'):
                warnings.warn("POTENTIAL ERROR: %s had a controller, but not a "
                              "'name' attribute." % node)
            for namespace in self.controllerStack:
                controllerFactory = getattr(namespace, 'wcfactory_' +
                                            controllerName, None)
                if controllerFactory is not None:
                    break
                controllerFactory = getattr(namespace, 'factory_' +
                                             controllerName, None)
                if controllerFactory is not None:
                    warnings.warn("factory_ methods are deprecated; please use "
                                  "wcfactory_ instead", DeprecationWarning)
                    break
            if controllerFactory is None:
                raise NotImplementedError("You specified controller name %s on "
                                          "a node, but no factory_%s method "
                                          "was found in %s." % (controllerName,
                                                            controllerName,
                                                            self.controllerStack 
                                                            + [input]))
            try:
                controller = controllerFactory(request, node, model)
            except TypeError:
                warnings.warn("A Controller Factory takes "
                              "(request, node, model) "
                              "now instead of (model)", DeprecationWarning)
                controller = controllerFactory(model)
        else:
            # If no "controller" attribute was specified on the node, see if 
            # there is a IController adapter registerred for the model.
            controller = components.getAdapter(
                            model, 
                            interfaces.IController, 
                            None,
                            components.getAdapterClassWithInheritance)
        if controller is None:
            controller = input.DefaultHandler(model)

        return controller
    
    def getNodeView(self, request, node, submodel, model):
        view = None   
        viewName = node.getAttribute('view')

        if model is None:
            model = self.getTopOfModelStack()
        
        # Look up a view factory.
        if viewName:
            for namespace in self.viewStack:
                viewMethod = getattr(namespace, 'wvfactory_' + viewName, None)
                if viewMethod is not None:
                    break
                viewMethod = getattr(namespace, 'factory_' + viewName, None)
                if viewMethod is not None:
                    warnings.warn("factory_ methods are deprecated; please use "
                                  "wvfactory_ instead", DeprecationWarning)
                    break

            try:
                view = viewMethod(request, node, model)
            except TypeError:
                warnings.warn("wvfactory_ methods take (request, node, "
                              "model) instead of (request, node) now. \n"
                              "Please instanciate your widgets with a "
                              "reference to model instead of self.model",
                              DeprecationWarning)
                self.model = model
                view = viewMethod(request, node)
                self.model = self.mainModel

            if view is None and not hasattr(self, 'wvupdate_' + viewName):
                raise NotImplementedError("You specified view name %s on a "
                                          "node, but no factory_%s method was "
                                          "found in %s or %s." % (viewName,
                                                                  viewName,
                                                                  self,
                                                                  widgets))
            # Look for wvupdate_ methods.
            for namespace in self.viewStack:
                if namespace is None: continue
                setupMethod = getattr(namespace, 'wvupdate_' + viewName, None)
                if setupMethod:
                    if view is None:
                        view = widgets.Widget(self.model)
                    view.setupMethods.append(setupMethod)
        elif node.getAttribute("model") and model is not self.model:
            # If no "view" attribute was specified on the node, see if there
            # is a IView adapter registerred for the model.
            # First, see if the model is Componentized.
            if isinstance(model, components.Componentized):
                view = model.getAdapter(interfaces.IView)
            if not view and hasattr(model, '__class__'):
                view = components.getAdapter(model, 
                                interfaces.IView, 
                                None,
                                components.getAdapterClassWithInheritance)

        if view is None:
            view = node
        return view

    def handleNode(self, request, node):
        if not hasattr(node, 'getAttribute'): # text node?
            return node
        
        submodelName = node.getAttribute('model')
        if submodelName is None:
            submodelName = ""
        model = self.getNodeModel(request, node, submodelName)
        controller = self.getNodeController(request, node, submodelName, model)
        controller.parent = self.controllerStack[0]
        self.controllerStack.insert(0, controller)
        view = self.getNodeView(request, node, submodelName, model)
        if not isinstance(view, type("")):
            view.parent = self.viewStack[0]
            if hasattr(view, 'model') and view.model != self.modelStack[0]:
                self.modelStack[0] = view.model
        self.viewStack.insert(0, view)
        if isinstance(view, widgets.Widget):
            id = node.getAttribute("id")
            if not id:
                id = "woven_id_" + str(self.currentId)
                self.currentId += 1
                view['id'] = id
            self.subviews[id] = view
        
        if isinstance(view, View):
            controller.setView(view)
        else:
            controller.setView(widgets.DefaultWidget(model))
        if not getattr(controller, 'submodel', None):
            controller.setSubmodel(submodelName)
        # xxx refactor this into a widget interface and check to see if the object implements IWidget
        # the view may be a deferred; this is why this check is required
        if hasattr(view, 'setController'):
            if model is None:
                model = self.getTopOfModelStack()
            model.addView(view)
            view.setController(controller)
            view.setNode(node)
            if not getattr(view, 'submodel', None):
                view.setSubmodel(submodelName)
        
        controllerResult = controller.handle(request)
        self.outstandingCallbacks += 1
        self.handleControllerResults(controllerResult, request, node, 
                                    controller, view, NO_DATA_YET)

    def handleControllerResults(self, controllerResult, request, node, 
                                controller, view, success):
        isCallback = success != NO_DATA_YET
        self.outstandingCallbacks -= 1
        if isinstance(controllerResult, type(())):
            success, data = controllerResult
        else:
            data = controllerResult
        if isinstance(data, defer.Deferred):
            self.outstandingCallbacks += 1
            data.addCallback(self.handleControllerResults, request, node, 
                                controller, view, success)
            data.addErrback(self.renderFailure, request)
            return data
        if success is not None:
            self.handlerResults[success].append((controller, data, node))
        
        returnNode = self.dispatchResult(request, node, view)
        if not isinstance(returnNode, defer.Deferred):
            self.recurseChildren(request, returnNode)
            self.modelStack.pop(0)
            self.viewStack.pop(0)
            self.controllerStack.pop(0)

        if isCallback and not self.outstandingCallbacks:
            log.msg("Sending page from controller callback!")
            self.sendPage(request)

    def sendPage(self, request):
        """
        Check to see if handlers recorded any errors before sending the page
        """
        failures = self.handlerResults.get(0, None)
        stop = 0
        if failures:
            stop = self.handleFailures(request, failures)
            self.handlerResults[0] = []
        if not stop:
            successes = self.handlerResults.get(1, None)
            if successes:
                process = self.handleSuccesses(request, successes)
                self.handlerResults[1] = []
                stop = self.controller.process(request, **process)
                if isinstance(stop, defer.Deferred):
                    stop.addCallback(self.handleProcessCallback, request)
                    stop.addErrback(self.renderFailure, request)
                    stop = template.STOP_RENDERING
    
        if not stop:
            log.msg("Sending page!")
            #sess = request.getSession(IWovenLivePage)
            #if sess:
            #    sess.setCurrentPage(self)
            page = str(self.d.toxml())
            request.write(page)
            request.finish()
            return page
        elif stop == template.RESTART_RENDERING:
            # Start the whole damn thing again with fresh state
            selfRef = request.pathRef()
            otherSelf = selfRef.getObject()
            otherSelf.render(request)

    def handleFailures(self, request, failures):
        log.msg("There were failures: ", failures)
        return 0

    def handleSuccesses(self, request, successes):
        log.msg("There were successes: ", successes)
        process = {}
        for controller, data, node in successes:
            process[str(node.getAttribute('name'))] = data
            if request.args.has_key(node.getAttribute('name')):
                del request.args[node.getAttribute('name')]
            result = controller.commit(request, node, data)
            returnNodes = controller.model.notify({'request': request, 
                                        controller.submodel: data})
            for newNode in returnNodes:
                if newNode is not None:
                    self.recurseChildren(request, newNode)
            if isinstance(result, defer.Deferred):
                self.outstandingCallbacks += 1
                result.addCallback(self.handleCommitCallback, request)
                result.addErrback(self.renderFailure, request)
        return process

    def handleCommitCallback(self, result, request):
        log.msg("Got a handle commit callback!")
        self.outstandingCallbacks -= 1
        if not self.outstandingCallbacks:
            log.msg("Sending page from commit callback!")
            self.sendPage(request)

    def handleProcessCallback(self, result, request):
        self.sendPage(request)

    def setSubviewFactory(self, name, factory, setup=None):
        setattr(self, "wvfactory_" + name, lambda request, node, m: 
                                                    factory(m))
        if setup:
            setattr(self, "wvupdate_" + name, setup)


#backwards compatibility
WView = View


def registerViewForModel(view, model):
    """
    Registers `view' as an adapter of `model' for L{interfaces.IView}.
    """
    components.registerAdapter(view, model, interfaces.IView)
#     adapter = components.getAdapter(model, resource.IResource, None)
#     if adapter is None and components.implements(view, resource.IResource):
#         components.registerAdapter(view, model, resource.IResource)



#sibling imports::

# If no widget/handler was found in the container controller or view, these
# modules will be searched.

import input
import widgets

