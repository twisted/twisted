
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
import controller
from utils import doSendPage, Stack
import model

# Twisted imports
from twisted.internet import defer
from twisted.python import components
from twisted.python import log
from twisted.web import resource, microdom


import warnings


NO_DATA_YET = 2


def viewFactory(viewClass):
    return lambda request, node, model: viewClass(model)

def viewMethod(viewClass):
    return lambda self, request, node, model: viewClass(model)


class View(template.DOMTemplate):

    __implements__ = (template.DOMTemplate.__implements__, interfaces.IView)
    # wvfactory_xxx method signature: request, node, model; returns Widget
    # wvupdate_xxx method signature: request, widget, data; mutates widget 
    #    based on data (not necessarily an IModel; 
    #    has been unwrapped at this point)

    wantsAllNotifications = 0

    viewLibraries = []
    setupStacks = 1
    def __init__(self, m, templateFile=None, controller=None, doneCallback=None, modelStack=None, viewStack=None, controllerStack=None):
        """
        A view must be told what its model is, and may be told what its
        controller is, but can also look up its controller if none specified.
        """
        if not components.implements(m, interfaces.IModel):
            m = model.adaptToIModel(m, None, None)
        self.model = self.mainModel = m
        # It's the responsibility of the calling code to make sure
        # setController is called on this view before it's rendered.
        self.controller = None
        self.subviews = {}
        if self.setupStacks:
            self.model.modelStack = Stack([self.model])
            self.setupViewStack()
            if doneCallback is None:
                self.doneCallback = doSendPage
            else:
                self.doneCallback = doneCallback
        self.setupMethods = []
        template.DOMTemplate.__init__(self, templateFile=templateFile)

    def setupViewStack(self):
        self.viewStack = Stack([])
        if widgets not in self.viewLibraries:
            self.viewLibraries.append(widgets)
        for library in self.viewLibraries:
            self.importViewLibrary(library)
        self.viewStack.push(self)

    def importViewLibrary(self, namespace):
        if not hasattr(namespace, 'getSubview'):
            namespace.getSubview = utils.createGetFunction(namespace)
        self.viewStack.push(namespace)
        return self

    def render(self, request, doneCallback=None, block=None):
        request.currentId = 0
        request.currentPage = self
        if self.controller is None:
            self.controller = controller.Controller(self.model)
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

    def generate(self, request, node):
        """Allow a view to be used like a widget. Will look up the template
        file and return it in place of the incoming node.
        """
        return self.lookupTemplate(request)

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
                m = self.model.modelStack.peek()
            else:
                for parent in self.model.modelStack:
                    if parent is None:
                        continue
                    m = parent.lookupSubmodel(submodel)
                    if m is not None:
                        #print "model", m
                        break
                else:
                    raise Exception("Node had a model=%s "
                                  "attribute, but the submodel was not "
                                  "found in %s." % (submodel,
                                  filter(lambda x: x, self.model.modelStack.stack)))
        else:
            m = None
        self.model.modelStack.push(m)
        if m:
#            print "M NAME", m.name
#             if parent is not m:
#                 m.parent = parent
#             if not getattr(m, 'name', None):
#                 m.name = submodel
            return m
        #print `submodel`, self.getTopOfModelStack()
        if submodel:
            return self.model.modelStack.peek()
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
            model = self.model.modelStack.peek()

        # Look up a controller factory.
        if controllerName:
            if not node.hasAttribute('name'):
                warnings.warn("POTENTIAL ERROR: %s had a controller, but not a "
                              "'name' attribute." % node)
            for namespace in self.controller.controllerStack:
                if namespace is None:
                    continue
                controller = namespace.getSubcontroller(request, node, model, controllerName)
                if controller is not None:
                    break
            else:
                raise NotImplementedError("You specified controller name %s on "
                                          "a node, but no wcfactory_%s method "
                                          "was found in %s." % (controllerName,
                                        controllerName,
                                        filter(lambda x: x, self.controller.controllerStack.stack)
                                        ))
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

        @returns L{widgets.Widget}
        """
        view = None
        vm = getattr(self, 'wvfactory_' + viewName, None)
        if vm is None:
            vm = getattr(self, 'factory_' + viewName, None)
            if vm is not None:
                warnings.warn("factory_ methods are deprecated; please use "
                              "wvfactory_ instead", DeprecationWarning)
        if vm:
            if vm.func_code.co_argcount == 3:
                 warnings.warn("wvfactory_ methods take (request, node, "
                               "model) instead of (request, node) now. \n"
                               "Please instanciate your widgets with a "
                               "reference to model instead of self.model",
                               DeprecationWarning)
                 self.model = model
                 view = vm(request, node)
                 self.model = self.mainModel
            else:
                view = vm(request, node, model)

        setupMethod = getattr(self, 'wvupdate_' + viewName, None)
        if setupMethod:
            if view is None:
                view = widgets.Widget(model)
            view.setupMethods.append(setupMethod)
        return view


    def getNodeView(self, request, node, submodel, model):
        view = None
        viewName = node.getAttribute('view')

        if model is None:
            model = self.model.modelStack.peek()

        # Look up a view factory.
        if viewName:
            for namespace in self.viewStack:
                if namespace is None:
                    continue
                try:
                    view = namespace.getSubview(request, node, model, viewName)
                except AttributeError:
                    # Was that from something in the viewStack that didn't
                    # have a getSubview?
                    if not hasattr(namespace, "getSubview"):
                        log.msg("Warning: There is no getSubview on %r" %
                                (namespace,))
                        continue
                    else:
                        # No, something else is really broken.
                        raise
                if view is not None:
                    break
            else:
                raise NotImplementedError(
                    "You specified view name %s on a node %s, but no "
                    "wvfactory_%s method was found in %s.  (Or maybe they were"
                    "found but they returned None.)" % (
                    viewName, node, viewName,
                    filter(lambda x: x,self.viewStack.stack)))
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
        return model

    def handleModel(self, model, request, node, submodelName):
        view = self.getNodeView(request, node, submodelName, model)
        controller = self.getNodeController(request, node, submodelName, model)
        if view or controller:
            if model is None:
                model = self.model.modelStack.peek()
            if not view or not isinstance(view, View):
                view = widgets.DefaultWidget(model, viewStack = self.viewStack.clone())
            else:
                view.viewStack = self.viewStack.clone()
            if not controller:
                controller = input.DefaultHandler(model, controllerStack = self.controller.controllerStack.clone())
            else:
                controller.controllerStack = self.controller.controllerStack.clone()
            controller.parent = self.controller.controllerStack.peek()

            if not isinstance(view, widgets.DefaultWidget):
                model.addView(view)
            submodelList = [x.name for x in self.model.modelStack.stack if x is not None and x.name]
            submodelList.reverse()
            submodelName = '/'.join(submodelList)
            if not getattr(view, 'submodel', None):
                view.submodel = submodelName

            theId = node.getAttribute("id")
            if not theId:
                theId = "woven_id_" + str(request.currentId)
                request.currentId += 1
                view.setupMethods.append(utils.createSetIdFunction(theId))
                #print "SET AN ID", theId
            self.subviews[theId] = view
            view.parent = self.viewStack.peek()
            # If a Widget was constructed directly with a model that so far
            # is not in modelspace, we should put it on the stack so other
            # Widgets below this one can find it.
            if view.model is not self.model.modelStack.peek():
                self.model.modelStack.poke(view.model)

            model.modelStack = self.model.modelStack.clone()

            view.setController(controller)
            view.setNode(node)

            if not getattr(controller, 'submodel', None):
                controller.setSubmodel(submodelName)
            # xxx refactor this into a widget interface and check to see if the object implements IWidget
            # the view may be a deferred; this is why this check is required
            controller.setView(view)
            cParent = self.controller.controllerStack.peek()
            if controller._parent is None or cParent != controller:
                controller._parent = cParent
            controllerResult = controller.handle(request)
        else:
            controllerResult = (None, None)

        self.controller.controllerStack.push(controller)
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

        returnNode = self.dispatchResult(request, node, view)
        self.handleNewNode(request, returnNode)
        
        if isCallback and not self.outstandingCallbacks:
            log.msg("Sending page from controller callback!")
            self.doneCallback(self, self.d, request)

    def handleNewNode(self, request, returnNode):
        if not isinstance(returnNode, defer.Deferred):
            self.recurseChildren(request, returnNode)
            self.model.modelStack.pop()
            self.viewStack.pop()
            self.controller.controllerStack.pop()

    def sendPage(self, request):
        """
        Check to see if handlers recorded any errors before sending the page
        """
        self.doneCallback(self, self.d, request)

    def setSubviewFactory(self, name, factory, setup=None, *args, **kwargs):
        setattr(self, "wvfactory_" + name, lambda request, node, m:
                                                    factory(m, *args, **kwargs))
        if setup:
            setattr(self, "wvupdate_" + name, setup)

    def __setitem__(self, key, value):
        pass

    def unlinkViews(self):
        print "unlinking views"
        self.model.removeView(self)
        for key, value in self.subviews.items():
            value.model.removeView(value)


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
        assert newNode is not None
        if isinstance(newNode, defer.Deferred):
            return newNode
        nodeMutator = template.NodeNodeMutator(newNode)
        return nodeMutator.generate(request, node)


components.registerAdapter(ViewNodeMutator, View, template.INodeMutator)
