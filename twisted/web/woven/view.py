
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


from twisted.web.woven import template
from twisted.python import components
from twisted.python import mvc
from twisted.python import log
from twisted.internet import defer

# If no widget/handler was found in the container controller or view, these modules will be searched.
from twisted.web.woven import input
from twisted.web.woven import widgets


class DefaultHandler(input.InputHandler):
    def handle(self, request):
        """
        By default, we don't do anything
        """
        return (None, None)


class DefaultWidget(widgets.Widget):
    def generate(self, request, node):
        """
        By default, we just return the node unchanged
        """
        return node


class WView(template.DOMTemplate):
    def getNodeController(self, request, node):
        controllerName = node.getAttribute('controller')
        
        # Look up an InputHandler
        controllerFactory = DefaultHandler
        if controllerName:
            namespaces = [self.controller]
            for namespace in namespaces:
                controllerFactory = getattr(self.controller, 'factory_' + controllerName, None)
                if controllerFactory is not None:
                    break
            if controllerFactory is None:
                controllerFactory = getattr(dominput, controllerName, None)
            if controllerFactory is None:
                nodeText = node.toxml()
                raise NotImplementedError, "You specified controller name %s on a node, but no factory_%s method was found." % (controllerName, controllerName)
        return controllerFactory(self.model)
    
    def getNodeView(self, request, node):     
        view = None   
        viewName = node.getAttribute('view')

        # Look up either a widget factory, or a dom-mutating method
        if viewName:
            viewMethod = getattr(self, 'factory_' + viewName, None)
            if viewMethod is None:
                view = getattr(widgets, viewName, None)
                if view is not None:
                    view = view(self.model)
            else:
                view = viewMethod(request, node)
            if view is None:
                nodeText = node.toxml()
                raise NotImplementedError, "You specified view name %s on a node, but no factory_%s method was found." % (viewName, viewName)
        else:
            view = node
        return view

    def handleNode(self, request, node):
        if not hasattr(node, 'getAttribute'): # text node?
            return node

        id = node.getAttribute('model')
        
        controller = self.getNodeController(request, node)
        result = self.getNodeView(request, node)

        submodel_prefix = node.getAttribute("_submodel_prefix")
        if submodel_prefix and id:
            submodel = "/".join([submodel_prefix, id])
        elif id:
            submodel = id
        elif submodel_prefix:
            submodel = submodel_prefix
        else:
            submodel = ""

        controller.setView(result)
        if not getattr(controller, 'submodel', None):
            controller.setSubmodel(submodel)
        # xxx refactor this into a widget interface and check to see if the object implements IWidget
        # the view may be a deferred; this is why this check is required
        if hasattr(result, 'setController'):
            result.setController(controller)
            result.setNode(node)
            if not getattr(result, 'submodel', None):
                result.setSubmodel(submodel)
        
        success, data = controller.handle(request)
        if success is not None:
            self.handlerResults[success].append((controller, data, node))

        returnNode = self.dispatchResult(request, node, result)
        if not isinstance(returnNode, defer.Deferred):
            self.recurseChildren(request, returnNode)

    def sendPage(self, request):
        """
        Check to see if handlers recorded any errors before sending the page
        """
        failures = self.handlerResults.get(0, None)
        stop = 0
        if failures:
            stop = self.handleFailures(request, failures)
        if not stop:
            successes = self.handlerResults.get(1, None)
            if successes:
                process = self.handleSuccesses(request, successes)
                stop = self.controller.process(request, **process)

        if not stop:
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
            controller.commit(request, node, data)
        return process

    def process(self, request, **kwargs):
        log.msg("Processing results: ", kwargs)
        return template.RESTART_RENDERING


def registerViewForModel(view, model):
    components.registerAdapter(view, model, mvc.IView)

