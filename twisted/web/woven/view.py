
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

# Sibling imports
import interfaces
import template
import utils

# Twisted imports
from twisted.internet import defer
from twisted.python import components
from twisted.python import log
from twisted.web import resource

NO_DATA_YET = 2


class View(template.DOMTemplate):

    __implements__ = (template.DOMTemplate.__implements__, interfaces.IView)

    def __init__(self, model):
        """
        A view must be told what its model is, and may be told what its
        controller is, but can also look up its controller if none specified.
        """
        self.model = model
        self.controller = self.controllerFactory(model)
        template.DOMTemplate.__init__(self, model)

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

    
    def getNodeModel(self, submodel):
        if submodel:
            modelGetter = widgets.DefaultWidget(self.model)
            modelGetter.setSubmodel(submodel)
            model = modelGetter.getData()
        else:
            model = None
        return model

    def getNodeController(self, request, node, submodel):
        controllerName = node.getAttribute('controller')
        
        # Look up an InputHandler
        controllerFactory = input.DefaultHandler
        if controllerName:
            if not node.hasAttribute('name'):
                log.msg("POTENTIAL ERROR: %s had a controller, but not a 'name' attribute." % node)
            namespaces = [self.controller]
            for namespace in namespaces:
                controllerFactory = getattr(namespace, 'factory_' + controllerName, None)
                if controllerFactory is not None:
                    break
            if controllerFactory is None:
                controllerFactory = getattr(input, controllerName, None)
            if controllerFactory is None:
                raise NotImplementedError, "You specified controller name %s on a node, but no factory_%s method was found in %s." % (controllerName, controllerName, namespaces + [input])
        else:
            # If no "controller" attribute was specified on the node, see if 
            # there is a IController adapter registerred for the model.
            model = self.getNodeModel(submodel)
            if hasattr(model, '__class__'):
                controllerFactory = components.getAdapterClassWithInheritance(
                                model.__class__, 
                                interfaces.IController, 
                                controllerFactory)
        try:
            return controllerFactory(request, node, self.model)
        except TypeError:
            log.write("DeprecationWarning: A Controller Factory takes (request, node, model) now instead of (model)\n")
            return controllerFactory(self.model)
    
    def getNodeView(self, request, node, submodel):
        view = None   
        viewName = node.getAttribute('view')

        # Look up either a widget factory, or a dom-mutating method
        if viewName:
            namespaces = [self]
            for namespace in namespaces:
                viewMethod = getattr(namespace, 'factory_' + viewName, None)
                if viewMethod is not None:
                    break

            if viewMethod is None:
                view = getattr(widgets, viewName, None)
                if view is not None:
                    view = view(self.model)

            else:
                view = viewMethod(request, node)


            if view is None:
                raise NotImplementedError, "You specified view name %s on a node, but no factory_%s method was found in %s or %s." % (viewName, viewName, self, widgets)
        else:
            # If no "view" attribute was specified on the node, see if there
            # is a IView adapter registerred for the model.
            model = self.getNodeModel(submodel)
            if hasattr(model, '__class__'):
                view = components.getAdapterClassWithInheritance(
                                model.__class__, 
                                interfaces.IView, 
                                None)
            if view is not None:
                view = view(self.model)
            else:
                view = node
        return view

    def handleNode(self, request, node):
        if not hasattr(node, 'getAttribute'): # text node?
            return node
        
        id = node.getAttribute('model')
        submodel_prefix = node.getAttribute("_submodel_prefix")
        if submodel_prefix and id:
            submodel = "/".join([submodel_prefix, id])
        elif id:
            submodel = id
        elif submodel_prefix:
            submodel = submodel_prefix
        else:
            submodel = ""

        controller = self.getNodeController(request, node, submodel)
        view = self.getNodeView(request, node, submodel)
        
        if isinstance(view, View):
            controller.setView(view)
        else:
            controller.setView(widgets.DefaultWidget(self.model))
        if not getattr(controller, 'submodel', None):
            controller.setSubmodel(submodel)
        # xxx refactor this into a widget interface and check to see if the object implements IWidget
        # the view may be a deferred; this is why this check is required
        if hasattr(view, 'setController'):
            if view.wantsAllNotifications:
                self.model.addView(view)
            else:
                self.model.addSubview(submodel, view)
            view.setController(controller)
            view.setNode(node)
            if not getattr(view, 'submodel', None):
                view.setSubmodel(submodel)
        
        controllerResult = controller.handle(request)
        self.outstandingCallbacks += 1
        self.handleControllerResults(controllerResult, request, node, controller, view, NO_DATA_YET)

    def handleControllerResults(self, controllerResult, request, node, controller, view, success):
        isCallback = success != NO_DATA_YET
        self.outstandingCallbacks -= 1
        if isinstance(controllerResult, type(())):
            success, data = controllerResult
        else:
            data = controllerResult
        if isinstance(data, defer.Deferred):
            self.outstandingCallbacks += 1
            data.addCallback(self.handleControllerResults, request, node, controller, view, success)
            data.addErrback(utils.renderFailure, request)
            return data
        if success is not None:
            self.handlerResults[success].append((controller, data, node))
        
        returnNode = self.dispatchResult(request, node, view)
        if not isinstance(returnNode, defer.Deferred):
            self.recurseChildren(request, returnNode)

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
                    stop.addErrback(utils.renderFailure, request)
                    stop = template.STOP_RENDERING
    
        if not stop:
            log.msg("Sending page!")
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
            returnNodes = self.model.notify({'request': request, controller.submodel: data})
            for newNode in returnNodes:
                if newNode is not None:
                    self.recurseChildren(request, newNode)
            if isinstance(result, defer.Deferred):
                self.outstandingCallbacks += 1
                result.addCallback(self.handleCommitCallback, request)
                result.addErrback(utils.renderFailure, request)
        return process

    def handleCommitCallback(self, result, request):
        log.msg("Got a handle commit callback!")
        self.outstandingCallbacks -= 1
        if not self.outstandingCallbacks:
            log.msg("Sending page from commit callback!")
            self.sendPage(request)

    def handleProcessCallback(self, result, request):
        self.sendPage(request)

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

