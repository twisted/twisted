
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


class Stack:
    def __init__(self, stack=None):
        if stack is None:
            self.stack = []
        else:
            self.stack = stack
    
    def push(self, item):
        self.stack.insert(0, item)
    
    def pop(self):
        return self.stack.pop(0)
    
    def peek(self):
        for x in self.stack:
            if x is not None:
                return x
    
    def poke(self, item):
        self.stack[0] = item
    
    def clone(self):
        return Stack(self.stack[:])

    def __len__(self):
        return len(self.stack)
    
    def __getitem__(self, item):
        return self.stack[item]


def doSendPage(self, d, request):
    log.msg("Sending page!")
    #sess = request.getSession(IWovenLivePage)
    #if sess:
    #    sess.setCurrentPage(self)
    page = str(d.toxml())
    request.write(page)
    request.finish()
    return page


class View(template.DOMTemplate):

    __implements__ = (template.DOMTemplate.__implements__, interfaces.IView)

    wantsAllNotifications = 0

    def __init__(self, m, templateFile=None, controller=None, doneCallback=None):
        """
        A view must be told what its model is, and may be told what its
        controller is, but can also look up its controller if none specified.
        """
        self.model = self.mainModel = model.adaptToIModel(m, None, None)
        self.modelStack = Stack([self.model])
        self.viewStack = Stack([self, widgets])
        self.subviews = {}
        self.currentId = 0
        if controller:
            self.controller = controller
        else:
            self.controller = self.controllerFactory(self.model)
        self.controllerStack = Stack([self.controller, input])
        if doneCallback is None:
            self.doneCallback = doSendPage
        else:
            self.doneCallback = doneCallback
        template.DOMTemplate.__init__(self, templateFile=templateFile)

    def render(self, request, doneCallback=None, block=None):
        if doneCallback is not None:
            self.doneCallback = doneCallback
        else:
            self.doneCallback = doSendPage
        return template.DOMTemplate.render(self, request, block=block)
        
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

    def generate(self, request, node):
        """Allow a view to be used like a widget. Will look up the template
        file and return it in place of the incoming node.
        """
        d = self.lookupTemplate(request)
        return d.firstChild()

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
        parent = None
        if submodel:
            if submodel == '.':
                m = self.modelStack.peek()
            else:
                for parent in self.modelStack:
                    if parent is None:
                        continue
                    m = parent.lookupSubmodel(submodel)
                    if m is not None:
                        #print "model", m
                        break
                else:
                    raise Exception("Node had a model=%s "
                                  "attribute, but the submodel was not "
                                  "found in %s." % (submodel, filter(lambda x: x, self.modelStack)))
                    m = self.modelStack.peek()
        else:
            m = None
        self.modelStack.push(m)
        if m:
            if parent is not m:
                m.parent = parent
            if not getattr(m, 'name', None):
                m.name = submodel
            return m
        #print `submodel`, self.getTopOfModelStack()
        if submodel:
            return self.modelStack.peek()
        return None

    def getNodeController(self, request, node, submodel, model):
        """
        Get a controller object to handle this node. If the node has no
        controller= attribute, first check to see if there is an IController
        adapter for our model.
        """
        controllerName = node.getAttribute('controller')
        controller = None

        if model is None:
            model = self.modelStack.peek()

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
                                                            filter(lambda x: x, self.controllerStack)
                                                            + [input]))
            try:
                controller = controllerFactory(request, node, model)
            except TypeError:
                warnings.warn("A Controller Factory takes "
                              "(request, node, model) "
                              "now instead of (model)", DeprecationWarning)
                controller = controllerFactory(model)
        elif node.getAttribute("model"):
            # If no "controller" attribute was specified on the node, see if
            # there is a IController adapter registerred for the model.
            controller = components.getAdapter(
                            model,
                            interfaces.IController,
                            None,
                            components.getAdapterClassWithInheritance)

        return controller


    def getSubview(self, request, node, model, viewName):
        """Get a sub-view from me.
        """
        view = None
        vm = getattr(self, 'wvfactory_' + viewName, None)
        if not vm:
            vm = getattr(self, 'factory_' + viewName, None)
            if vm is not None:
                warnings.warn("factory_ methods are deprecated; please use "
                              "wvfactory_ instead", DeprecationWarning)
        if vm:
            try:
                view = vm(request, node, model)
            except TypeError:
                 warnings.warn("wvfactory_ methods take (request, node, "
                               "model) instead of (request, node) now. \n"
                               "Please instanciate your widgets with a "
                               "reference to model instead of self.model",
                               DeprecationWarning)
                 self.model = model
                 view = vm(request, node)
                 self.model = self.mainModel

        setupMethod = getattr(self, 'wvupdate_' + viewName, None)
        if setupMethod:
            if view is None:
                view = widgets.Widget(self.model)
            view.setupMethods.append(setupMethod)
        return view


    def getNodeView(self, request, node, submodel, model):
        view = None
        viewName = node.getAttribute('view')

        if model is None:
            model = self.modelStack.peek()

        # Look up a view factory.
        if viewName:
            for namespace in self.viewStack:
                if namespace is None:
                    continue
                view = namespace.getSubview(request, node, model, viewName)
                if view is not None:
                    break
            if view is None:

                raise NotImplementedError("You specified view name %s on a "
                                          "node, but no factory_%s method was "
                                          "found in %s." % (viewName,
                                                                   viewName,
                                                                  filter(lambda x: x,self.viewStack)))
        elif node.getAttribute("model"):
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

        return view

    def handleNode(self, request, node):
        if not hasattr(node, 'getAttribute'): # text node?
            return node

        submodelName = node.getAttribute('model')
        if submodelName is None:
            submodelName = ""
        model = self.getNodeModel(request, node, submodelName)

        if isinstance(model, defer.Deferred):
            model.addCallback(self.handleModelLater,
                              request, node, submodelName)
            self.outstandingCallbacks += 1
        else:
            self.handleModel(model, request, node, submodelName)

    def handleModelLater(self, model, request, node, submodelName):
        self.outstandingCallbacks -= 1
        self.handleModel(model, request, node, submodelName)
        if not self.outstandingCallbacks:
            self.sendPage(request)

    def handleModel(self, model, request, node, submodelName):
        view = self.getNodeView(request, node, submodelName, model)
        controller = self.getNodeController(request, node, submodelName, model)

        if view or controller:
            if model is None:
                model = self.modelStack.peek()
            if not view or not isinstance(view, View):
                view = widgets.DefaultWidget(model)
            if not controller:
                controller = input.DefaultHandler(model)
            controller.parent = self.controllerStack[0]

            if not isinstance(view, widgets.DefaultWidget):
                model.addView(view)
            
            if not getattr(view, 'submodel', None):
                view.setSubmodel(submodelName)

#             id = node.getAttribute("id")
#             if not id:
#                 id = "woven_id_" + str(self.currentId)
#                 self.currentId += 1
#                 view['id'] = id
#             self.subviews[id] = view
            view.parent = self.viewStack.peek()
            # If a Widget was constructed directly with a model that so far
            # is not in modelspace, we should put it on the stack so other
            # Widgets below this one can find it.
            if view.model is not self.modelStack.peek():
                self.modelStack.poke(view.model)

            view.modelStack = self.modelStack.clone()
            view.viewStack = self.viewStack.clone()
            view.controllerStack = self.controllerStack.clone()

            view.setController(controller)
            view.setNode(node)

            if not getattr(controller, 'submodel', None):
                controller.setSubmodel(submodelName)
            # xxx refactor this into a widget interface and check to see if the object implements IWidget
            # the view may be a deferred; this is why this check is required
            controller.setView(view)
            controller._parent = self.controllerStack.peek()
            controllerResult = controller.handle(request)
        else:
            controllerResult = (None, None)

        self.controllerStack.push(controller)
        self.viewStack.push(view)
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
            self.modelStack.pop()
            self.viewStack.pop()
            self.controllerStack.pop()

        if isCallback and not self.outstandingCallbacks:
            log.msg("Sending page from controller callback!")
            self.doneCallback(self, self.d, request)

    def sendPage(self, request):
        """
        Check to see if handlers recorded any errors before sending the page
        """
        self.doneCallback(self, self.d, request)

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


class ViewNodeMutator(template.NodeMutator):
    """A ViewNodeMutator replaces the node that is passed into generate
    with the result of generating the View it adapts.
    """
    def generate(self, request, node):
        newNode = self.data.generate(request, node)
        if isinstance(newNode, defer.Deferred):
            return newNode
        nodeMutator = template.NodeNodeMutator(newNode)
        return nodeMutator.generate(request, node)


components.registerAdapter(ViewNodeMutator, View, template.INodeMutator)
