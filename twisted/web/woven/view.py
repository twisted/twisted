# -*- test-case-name: twisted.test.test_woven -*-
#
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

__version__ = "$Revision: 1.73 $"[11:-2]

# Sibling imports
import interfaces
import template
import utils
import controller
from utils import doSendPage
import model

# Twisted imports
from twisted.internet import defer
from twisted.python import components
from twisted.python import log
from twisted.web import resource, microdom, html, error
from twisted.web.server import NOT_DONE_YET


import os
import sys
import stat
import warnings
import types


def peek(stack):
    if stack is None:
        return None
    it = None
    while it is None and stack is not None:
        it, stack = stack
    return it


def poke(stack, new):
    it, stack = stack
    return (new, stack)


def filterStack(stack):
    returnVal = []
    while stack is not None:
        it, stack = stack
        if it is not None:
            returnVal.append(it)
    return returnVal


NO_DATA_YET = 2


def viewFactory(viewClass):
    return lambda request, node, model: viewClass(model)

def viewMethod(viewClass):
    return lambda self, request, node, model: viewClass(model)


class View:

    __implements__ = (resource.IResource, interfaces.IView)
    # wvfactory_xxx method signature: request, node, model; returns Widget
    # wvupdate_xxx method signature: request, widget, data; mutates widget 
    #    based on data (not necessarily an IModel; 
    #    has been unwrapped at this point)

    wantsAllNotifications = 0
    templateFile = ''
    templateDirectory = ''
    template = ''

    isLeaf = 1

    def getChild(self, path, request):
        return error.NoResource("No such child resource.")

    def getChildWithDefault(self, path, request):
        return self.getChild(path, request)

    viewLibraries = []
    setupStacks = 1
    doneCallback = None
    def __init__(self, m, templateFile=None, templateDirectory=None, template=None, controller=None, doneCallback=None, modelStack=None, viewStack=None, controllerStack=None):
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
            self.modelStack = None
            self.viewStack = None
            self.controllerStack = None
            if doneCallback is None and self.doneCallback is None:
                self.doneCallback = doSendPage
            else:
                print "DoneCallback", doneCallback
                self.doneCallback = doneCallback
        if template is not None:
            self.template = template
        if templateFile is not None:
            self.templateFile = templateFile
        if templateDirectory is not None:
            self.templateDirectory = templateDirectory

        self.outstandingCallbacks = 0
        self.outstandingNodes = []
        self.failed = 0
        self.setupMethods = []

    def setupAllStacks(self):
        self.modelStack = (self.model, None)
        self.controllerStack = (self.controller, (input, None))
        self.setupViewStack()
        
    def setUp(self, request, d):
        pass

    def setupViewStack(self):
        self.viewStack = None
        if widgets not in self.viewLibraries:
            self.viewLibraries.append(widgets)
        for library in self.viewLibraries:
            if not hasattr(library, 'getSubview'):
                library.getSubview = utils.createGetFunction(library)
            self.viewStack = (library, self.viewStack)
        self.viewStack = (self, self.viewStack)

    def importViewLibrary(self, namespace):
        self.viewLibraries.append(namespace)
        return self

    def render(self, request, doneCallback=None):
        if not getattr(request, 'currentId', 0):
            request.currentId = 0
        request.currentPage = self
        if self.controller is None:
            self.controller = controller.Controller(self.model)
        if doneCallback is not None:
            self.doneCallback = doneCallback
        else:
            self.doneCallback = doSendPage
        self.setupAllStacks()
        template = self.getTemplate(request)
        if template:
            self.d = microdom.parseString(template)
        else:
            if not self.templateFile:
                raise AttributeError, "%s does not define self.templateFile to operate on" % self.__class__
            self.d = self.lookupTemplate(request)
        request.d = self.d
        self.handleDocument(request, self.d)
        return NOT_DONE_YET

    def getTemplate(self, request):
        """
        Override this if you want to have your subclass look up its template
        using a different method.
        """
        return self.template

    def lookupTemplate(self, request):
        """
        Use acquisition to look up the template named by self.templateFile,
        located anywhere above this object in the heirarchy, and use it
        as the template. The first time the template is used it is cached
        for speed.
        """
        if self.template:
            return microdom.parseString(self.template)
        if not self.templateDirectory:
            mod = sys.modules[self.__module__]
            if hasattr(mod, '__file__'):
                self.templateDirectory = os.path.split(mod.__file__)[0]
        # First see if templateDirectory + templateFile is a file
        templatePath = os.path.join(self.templateDirectory, self.templateFile)
        if not os.path.exists(templatePath):
            templatePath = None
        if not templatePath:
            # If not, use acquisition to look for the name above this object
            # look up an object named by our template data member
            templateRef = request.pathRef().locate(self.templateFile)
            # Build a reference to the template on disk
            self.templateDirectory = templateRef.parentRef().getObject().path
            templatePath = os.path.join(self.templateDirectory, self.templateFile)
        # Check to see if there is an already compiled copy of it
        templateName = os.path.splitext(self.templateFile)[0]
        compiledTemplateName = '.' + templateName + '.pxp'
        compiledTemplatePath = os.path.join(self.templateDirectory, compiledTemplateName)
        # No? Compile and save it
        if (not os.path.exists(compiledTemplatePath) or
        os.stat(compiledTemplatePath)[stat.ST_MTIME] < os.stat(templatePath)[stat.ST_MTIME]):
            compiledTemplate = microdom.parse(templatePath)
            from cPickle import dump
            dump(compiledTemplate, open(compiledTemplatePath, 'wb'), 1)
#            parent = templateRef.parentRef().getObject()
#            parent.savePickleChild(compiledTemplatePath, compiledTemplate)
        else:
            from cPickle import load
            compiledTemplate = load(open(compiledTemplatePath, "rb"))
        return compiledTemplate

    def handleDocument(self, request, document):
        """Handle the root node, and send the page if there are no
        outstanding callbacks when it returns.
        """
        try:
            request.d = document
            self.setUp(request, document)
            # Don't let outstandingCallbacks get to 0 until the
            # entire tree has been recursed
            # If you don't do this, and any callback has already
            # completed by the time the dispatchResultCallback
            # is added in dispachResult, then sendPage will be
            # called prematurely within dispatchResultCallback
            # resulting in much gnashing of teeth.
            self.outstandingNodes = document.childNodes[:] + [1]
            self.outstandingNodes.reverse()

            self.outstandingCallbacks += 1
            self.handleOutstanding(request)
            self.outstandingCallbacks -= 1
            if not self.outstandingCallbacks:
                return self.sendPage(request)
        except:
            self.renderFailure(None, request)

    def handleOutstanding(self, request):
        while self.outstandingNodes:
            node = self.outstandingNodes.pop()
            if node is 1:
                self.modelStack = self.modelStack[1]
                self.viewStack = self.viewStack[1]
                if self.controllerStack is not None:
                    self.controllerStack = self.controllerStack[1]
            if (hasattr(node, 'getAttribute') and 
            (node.getAttribute('model') or node.getAttribute('view') or node.getAttribute('controller'))):
                self.outstandingNodes.append(1)
                self.handleNode(request, node)
            else:
                if hasattr(node, 'getAttribute') and (node.getAttribute('view') or node.getAttribute('controller')):
                    self.outstandingNodes.append(node)
                if hasattr(node, 'childNodes') and node.childNodes:
                    self.recurseChildren(request, node)
        
    def recurseChildren(self, request, node):
        """If this node has children, handle them.
        """
        new = node.childNodes[:]
        new.reverse()
        self.outstandingNodes.extend(new)

    def dispatchResult(self, request, node, result):
        """Check a given result from handling a node and look up a NodeMutator
        adapter which will convert the result into a node and insert it
        into the DOM tree. Return the new node.
        """
        if not isinstance(result, defer.Deferred):
            adapter = components.getAdapter(result, template.INodeMutator, None, components.getAdapterClassWithInheritance)
            if adapter is None:
                raise NotImplementedError(
                    "Your factory method returned %s, but there is no "
                    "INodeMutator adapter registerred for %s." %
                    (result, getattr(result, "__class__",
                                     None) or type(result)))
            result = adapter.generate(request, node)
        if isinstance(result, defer.Deferred):
            self.outstandingCallbacks += 1
            result.addCallback(self.dispatchResultCallback, request, node)
            result.addErrback(self.renderFailure, request)
            # Got to wait until the callback comes in
        return result

    def modelChanged(self, changed):
        """Dispatch changed messages to any update_* methods which
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
        return self.lookupTemplate(request).childNodes[0]

    def setController(self, controller):
        self.controller = controller
        self.controllerStack = (controller, self.controllerStack)

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
                m = peek(self.modelStack)
            else:
                modelStack = self.modelStack
                while modelStack is not None:
                    parent, modelStack = modelStack
                    if parent is None:
                        continue
                    m = parent.lookupSubmodel(request, submodel)
                    if m is not None:
                        #print "model", m
                        break
                else:
                    raise Exception("Node had a model=%s "
                                  "attribute, but the submodel was not "
                                  "found in %s." % (submodel,
                                  filterStack(self.modelStack)))
        else:
            m = None
        self.modelStack = (m, self.modelStack)
        if m is not None:
#            print "M NAME", m.name
#             if parent is not m:
#                 m.parent = parent
#             if not getattr(m, 'name', None):
#                 m.name = submodel
            return m
        #print `submodel`, self.getTopOfModelStack()
        if submodel:
            return peek(self.modelStack)
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
            model = peek(self.modelStack)

        # Look up a controller factory.
        if controllerName:
            #if not node.hasAttribute('name'):
            #    warnings.warn("POTENTIAL ERROR: %s had a controller, but not a "
            #                  "'name' attribute." % node)
            controllerStack = self.controllerStack
            while controllerStack is not None:
                namespace, controllerStack = controllerStack
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
                                        filterStack(self.controllerStack)
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

        @returns: L{widgets.Widget}
        """
        view = None
        vm = getattr(self, 'wvfactory_' + viewName, None)
        if vm is None:
            vm = getattr(self, 'factory_' + viewName, None)
            if vm is not None:
                warnings.warn("factory_ methods are deprecated; please use "
                              "wvfactory_ instead", DeprecationWarning)
        if vm:
            if vm.func_code.co_argcount == 3 and not type(vm) == types.LambdaType:
                 warnings.warn("wvfactory_ methods take (request, node, "
                               "model) instead of (request, node) now. \n"
                               "Please instantiate your widgets with a "
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
            model = peek(self.modelStack)

        # Look up a view factory.
        if viewName:
            viewStack = self.viewStack
            while viewStack is not None:
                namespace, viewStack = viewStack
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
                    filterStack(self.viewStack)))
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
        submodelName = node.getAttribute('model')
        if submodelName is None:
            submodelName = ""
        model = self.getNodeModel(request, node, submodelName)
        view = self.getNodeView(request, node, submodelName, model)
        controller = self.getNodeController(request, node, submodelName, model)
        if view or controller:
            if model is None:
                model = peek(self.modelStack)
            if not view or not isinstance(view, View):
                view = widgets.DefaultWidget(model)

            if not controller:
                controller = input.DefaultHandler(model)

            if not isinstance(view, widgets.DefaultWidget):
                model.addView(view)
            submodelList = [x.name for x in filterStack(self.modelStack) if x.name]
            submodelList.reverse()
            submodelName = '/'.join(submodelList)
            if not getattr(view, 'submodel', None):
                view.submodel = submodelName

            theId = node.getAttribute("id")
            if not theId:
                curId = getattr(request, 'currentId', 0)
                theId = "woven_id_" + str(curId)
                request.currentId = curId + 1
                view.setupMethods.append(utils.createSetIdFunction(theId))
                view.outgoingId = theId
                #print "SET AN ID", theId
            self.subviews[theId] = view
            view.parent = peek(self.viewStack)
            # If a Widget was constructed directly with a model that so far
            # is not in modelspace, we should put it on the stack so other
            # Widgets below this one can find it.
            if view.model is not peek(self.modelStack):
                self.modelStack = poke(self.modelStack, view.model)

            cParent = peek(self.controllerStack)
            if controller._parent is None or cParent != controller:
                controller._parent = cParent

            self.controllerStack = (controller, self.controllerStack)
            self.viewStack = (view, self.viewStack)

            view.viewStack = self.viewStack
            view.controllerStack = self.controllerStack
            view.modelStack = self.modelStack

            view.setController(controller)
            view.setNode(node)

            if not getattr(controller, 'submodel', None):
                controller.setSubmodel(submodelName)

            controller.setView(view)
            controller.setNode(node)

            controllerResult = controller.handle(request)
            controllerResult = (None, None)
        else:
            self.controllerStack = (controller, self.controllerStack)
            self.viewStack = (view, self.viewStack)

            controllerResult = (None, None)

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
        else:
            # TODO: Handle deferreds here.
            pass

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

    def dispatchResultCallback(self, result, request, node):
        """Deal with a callback from a deferred, dispatching the result
        and recursing children.
        """
        self.outstandingCallbacks -= 1
        node = self.dispatchResult(request, node, result)
        self.recurseChildren(request, node)
        if not self.outstandingCallbacks:
            return self.sendPage(request)

    def renderFailure(self, failure, request):
        try:
            xml = request.d.toprettyxml()
        except:
            xml = ""
#         if not hasattr(request, 'channel'):
#             log.msg("The request got away from me before I could render an error page.")
#             log.err(failure)
#             return failure
        if not self.failed:
            self.failed = 1
            if failure:
                request.write("<html><head><title>%s: %s</title></head><body>\n" % (html.escape(str(failure.type)), html.escape(str(failure.value))))
            else:
                request.write("<html><head><title>Failure!</title></head><body>\n")
            utils.renderFailure(failure, request)
            request.write("<h3>Here is the partially processed DOM:</h3>")
            request.write("\n<pre>\n")
            request.write(html.escape(xml))
            request.write("\n</pre>\n")
            request.write("</body></html>")
            request.finish()
        return failure


class LiveView(View):
    def wvfactory_webConduitGlue(self, request, node, m):
        if request.getHeader("user-agent").count("MSIE"):
            return View(m, templateFile="FlashConduitGlue.html")
        else:
            return View(m, templateFile="WebConduitGlue.html")

    def wvupdate_woven_flashConduitSessionView(self, request, wid, mod):
        #print "updating flash thingie"
        uid = request.getSession().uid
        n = wid.templateNode
        if n.hasAttribute('src'):
            n.setAttribute('src', n.getAttribute('src') + '?twisted_session=' + str(uid))
        else:
            n.setAttribute('value', n.getAttribute('value') + '?twisted_session=' + str(uid))
        #print wid.templateNode.toxml()


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
            if hasattr(self.data, 'outgoingId'):
                # Let dispatchResult know what ID we want to insert into 
                # the outgoing document, so we can replace it later
                newNode.outgoingId = self.data.outgoingId
            return newNode
        nodeMutator = template.NodeNodeMutator(newNode)
        return nodeMutator.generate(request, node)


components.registerAdapter(ViewNodeMutator, View, template.INodeMutator)
