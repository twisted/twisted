# -*- test-case-name: twisted.web.test.test_woven -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from __future__ import nested_scopes

__version__ = "$Revision: 1.67 $"[11:-2]

import os
import cgi
import types

from twisted.python import log
from twisted.python import components
from twisted.python import failure
from zope.interface import implements
from twisted.web import resource, server, static
from twisted.web.woven import interfaces, utils
from twisted.web import woven
from twisted.web import microdom
from twisted.web.static import redirectTo, addSlash

import warnings
from time import time as now

def controllerFactory(controllerClass):
    return lambda request, node, model: controllerClass(model)

def controllerMethod(controllerClass):
    return lambda self, request, node, model: controllerClass(model)


class Controller(resource.Resource):
    """
    A Controller which handles to events from the user. Such events
    are `web request', `form submit', etc.

    I should be the IResource implementor for your Models (and
    L{registerControllerForModel} makes this so).
    """

    implements(interfaces.IController)
    setupStacks = 1
    addSlash = 1 # Should this controller add a slash to the url automatically?
    controllerLibraries = []
    viewFactory = None
    templateDirectory = ""
    def __init__(self, m, inputhandlers=None, view=None, controllers=None, templateDirectory = None):
        #self.start = now()
        resource.Resource.__init__(self)
        self.model = m
        # It's the responsibility of the calling code to make sure setView is
        # called on this controller before it's rendered.
        self.view = None
        self.subcontrollers = []
        if self.setupStacks:
            self.setupControllerStack()
        if inputhandlers is None and controllers is None:
            self._inputhandlers = []
        elif inputhandlers:
            print "The inputhandlers arg is deprecated, please use controllers instead"
            self._inputhandlers = inputhandlers
        else:
            self._inputhandlers = controllers
        if templateDirectory is not None:
            self.templateDirectory = templateDirectory
        self._valid = {}
        self._invalid = {}
        self._process = {}
        self._parent = None

    def setupControllerStack(self):
        self.controllerStack = utils.Stack([])
        from twisted.web.woven import input
        if input not in self.controllerLibraries:
            self.controllerLibraries.append(input)
        for library in self.controllerLibraries:
            self.importControllerLibrary(library)
        self.controllerStack.push(self)
    
    def importControllerLibrary(self, namespace):
        if not hasattr(namespace, 'getSubcontroller'):
            namespace.getSubcontroller = utils.createGetFunction(namespace)
        self.controllerStack.push(namespace)

    def getSubcontroller(self, request, node, model, controllerName):
        controller = None
        cm = getattr(self, 'wcfactory_' +
                                    controllerName, None)
        if cm is None:
            cm = getattr(self, 'factory_' +
                                         controllerName, None)
            if cm is not None:
                warnings.warn("factory_ methods are deprecated; please use "
                              "wcfactory_ instead", DeprecationWarning)
        if cm:
            if cm.func_code.co_argcount == 1 and not type(cm) == types.LambdaType:
                warnings.warn("A Controller Factory takes "
                              "(request, node, model) "
                              "now instead of (model)", DeprecationWarning)
                controller = controllerFactory(model)
            else:
                controller = cm(request, node, model)
        return controller

    def setSubcontrollerFactory(self, name, factory, setup=None):
        setattr(self, "wcfactory_" + name, lambda request, node, m:
                                                    factory(m))

    def setView(self, view):
        self.view = view

    def setNode(self, node):
        self.node = node

    def setUp(self, request, *args):
        """
        @type request: L{twisted.web.server.Request}
        """
        pass

    def getChild(self, name, request):
        """
        Look for a factory method to create the object to handle the
        next segment of the URL. If a wchild_* method is found, it will
        be called to produce the Resource object to handle the next
        segment of the path. If a wchild_* method is not found,
        getDynamicChild will be called with the name and request.

        @param name: The name of the child being requested.
        @type name: string
        @param request: The HTTP request being handled.
        @type request: L{twisted.web.server.Request}
        """
        if not name:
            method = "index"
        else:
            method = name.replace('.', '_')
        f = getattr(self, "wchild_%s" % method, None)
        if f:
            return f(request)
        else:
            child = self.getDynamicChild(name, request)
            if child is None:
                return resource.Resource.getChild(self, name, request)
            else:
                return child

    def getDynamicChild(self, name, request):
        """
        This method is called when getChild cannot find a matching wchild_*
        method in the Controller. Override me if you wish to have dynamic
        handling of child pages. Should return a Resource if appropriate.
        Return None to indicate no resource found.

        @param name: The name of the child being requested.
        @type name: string
        @param request: The HTTP request being handled.
        @type request: L{twisted.web.server.Request}
        """
        pass

    def wchild_index(self, request):
        """By default, we return ourself as the index.
        Override this to provide different behavior
        for a URL that ends in a slash.
        """
        self.addSlash = 0
        return self

    def render(self, request):
        """
        Trigger any inputhandlers that were passed in to this Page,
        then delegate to the View for traversing the DOM. Finally,
        call gatheredControllers to deal with any InputHandlers that
        were constructed from any controller= tags in the
        DOM. gatheredControllers will render the page to the browser
        when it is done.
        """
        if self.addSlash and request.uri.split('?')[0][-1] != '/':
            return redirectTo(addSlash(request), request)
        # Handle any inputhandlers that were passed in to the controller first
        for ih in self._inputhandlers:
            ih._parent = self
            ih.handle(request)
        self._inputhandlers = []
        for key, value in self._valid.items():
            key.commit(request, None, value)
        self._valid = {}
        return self.renderView(request)

    def makeView(self, model, templateFile=None, parentCount=0):
        if self.viewFactory is None:
            self.viewFactory = self.__class__
        v = self.viewFactory(model, templateFile=templateFile, templateDirectory=self.templateDirectory)
        v.parentCount = parentCount
        v.tapestry = self
        v.importViewLibrary(self)
        return v

    def renderView(self, request):
        if self.view is None:
            if self.viewFactory is not None:
                self.setView(self.makeView(self.model, None))
            else:
                self.setView(interfaces.IView(self.model, None))
            self.view.setController(self)
        return self.view.render(request, doneCallback=self.gatheredControllers)

    def gatheredControllers(self, v, d, request):
        process = {}
        request.args = {}
        for key, value in self._valid.items():
            key.commit(request, None, value)
            process[key.submodel] = value
        self.process(request, **process)
        #log.msg("Sending page!")
        self.pageRenderComplete(request)
        utils.doSendPage(v, d, request)
        #v.unlinkViews()

        #print "Page time: ", now() - self.start
        #return view.View.render(self, request, block=0)

    def aggregateValid(self, request, input, data):
        self._valid[input] = data
        
    def aggregateInvalid(self, request, input, data):
        self._invalid[input] = data

    def process(self, request, **kwargs):
        if kwargs:
            log.msg("Processing results: ", kwargs)

    def setSubmodel(self, submodel):
        self.submodel = submodel

    def handle(self, request):
        """
        By default, we don't do anything
        """
        pass

    def exit(self, request):
        """We are done handling the node to which this controller was attached.
        """
        pass

    def domChanged(self, request, widget, node):
        parent = getattr(self, '_parent', None)
        if parent is not None:
            parent.domChanged(request, widget, node)

    def pageRenderComplete(self, request):
        """Override this to recieve notification when the view rendering
        process is complete.
        """
        pass

WOVEN_PATH = os.path.split(woven.__file__)[0]

class LiveController(Controller):
    """A Controller that encapsulates logic that makes it possible for this
    page to be "Live". A live page can have it's content updated after the
    page has been sent to the browser, and can translate client-side
    javascript events into server-side events.
    """
    pageSession = None
    def render(self, request):
        """First, check to see if this request is attempting to hook up the
        output conduit. If so, do it. Otherwise, unlink the current session's
        View from the MVC notification infrastructure, then render the page
        normally.
        """
        # Check to see if we're hooking up an output conduit
        sess = request.getSession(interfaces.IWovenLivePage)
        #print "REQUEST.ARGS", request.args
        if request.args.has_key('woven_hookupOutputConduitToThisFrame'):
            sess.hookupOutputConduit(request)
            return server.NOT_DONE_YET
        if request.args.has_key('woven_clientSideEventName'):
            try:
                request.d = microdom.parseString('<xml/>', caseInsensitive=0, preserveCase=0)
                eventName = request.args['woven_clientSideEventName'][0]
                eventTarget = request.args['woven_clientSideEventTarget'][0]
                eventArgs = request.args.get('woven_clientSideEventArguments', [])
                #print "EVENT", eventName, eventTarget, eventArgs
                return self.clientToServerEvent(request, eventName, eventTarget, eventArgs)
            except:
                fail = failure.Failure()
                self.view.renderFailure(fail, request)
                return server.NOT_DONE_YET

        # Unlink the current page in this user's session from MVC notifications
        page = sess.getCurrentPage()
        #request.currentId = getattr(sess, 'currentId', 0)
        if page is not None:
            page.view.unlinkViews()
            sess.setCurrentPage(None)
        #print "PAGE SESSION IS NONE"
        self.pageSession = None
        return Controller.render(self, request)

    def clientToServerEvent(self, request, eventName, eventTarget, eventArgs):
        """The client sent an asynchronous event to the server.
        Locate the View object targeted by this event and attempt
        to call onEvent on it.
        """
        sess = request.getSession(interfaces.IWovenLivePage)
        self.view = sess.getCurrentPage().view
        #request.d = self.view.d
        print "clientToServerEvent", eventTarget
        target = self.view.subviews[eventTarget]
        print "target, parent", target, target.parent
        #target.parent = self.view
        #target.controller._parent = self

        ## From the time we call onEvent until it returns, we want all
        ## calls to IWovenLivePage.sendScript to be appended to this
        ## list so we can spit them out in the response, immediately
        ## below.
        scriptOutput = []
        orig = sess.sendScript
        sess.sendScript = scriptOutput.append
        target.onEvent(request, eventName, *eventArgs)
        sess.sendScript = orig

        scriptOutput.append('parent.woven_clientToServerEventComplete()')        
        
        #print "GATHERED JS", scriptOutput

        return '''<html>
<body>
    <script language="javascript">
    %s
    </script>
    %s event sent to %s (%s) with arguments %s.
</body>
</html>''' % ('\n'.join(scriptOutput), eventName, cgi.escape(str(target)), eventTarget, eventArgs)

    def gatheredControllers(self, v, d, request):
        Controller.gatheredControllers(self, v, d, request)
        sess = request.getSession(interfaces.IWovenLivePage)
        self.pageSession = sess
        sess.setCurrentPage(self)
        sess.currentId = request.currentId

    def domChanged(self, request, widget, node):
        sess = request.getSession(interfaces.IWovenLivePage)
        print "domchanged"
        if sess is not None:
            if not hasattr(node, 'getAttribute'):
                return
            page = sess.getCurrentPage()
            if page is None:
                return
            nodeId = node.getAttribute('id')
            #logger.warn("DOM for %r is changing to %s", nodeId, node.toprettyxml())
            nodeXML = node.toxml()
            nodeXML = nodeXML.replace("\\", "\\\\")
            nodeXML = nodeXML.replace("'", "\\'")
            nodeXML = nodeXML.replace('"', '\\"')
            nodeXML = nodeXML.replace('\n', '\\n')
            nodeXML = nodeXML.replace('\r', ' ')
            nodeXML = nodeXML.replace('\b', ' ')
            nodeXML = nodeXML.replace('\t', ' ')
            nodeXML = nodeXML.replace('\000', ' ')
            nodeXML = nodeXML.replace('\v', ' ')
            nodeXML = nodeXML.replace('\f', ' ')

            js = "parent.woven_replaceElement('%s', '%s')" % (nodeId, nodeXML)
            #for key in widget.subviews.keys():
            #    view.subviews[key].unlinkViews()
            oldNode = page.view.subviews[nodeId]
            for id, subview in oldNode.subviews.items():
                subview.unlinkViews()
            topSubviews = page.view.subviews
            #print "Widgetid, subviews", id(widget), widget.subviews
            if widget.subviews:
                def recurseSubviews(w):
                    #print "w.subviews", w.subviews
                    topSubviews.update(w.subviews)
                    for id, sv in w.subviews.items():
                        recurseSubviews(sv)
                #print "recursing"
                recurseSubviews(widget)
                #page.view.subviews.update(widget.subviews)
            sess.sendScript(js)

    def wchild_WebConduit2_js(self, request):
        #print "returning js file"
        h = request.getHeader("user-agent")
        if h.count("MSIE"):
            fl = "WebConduit2_msie.js"
        else:
            fl = "WebConduit2_mozilla.js"

        return static.File(os.path.join(WOVEN_PATH, fl))

    def wchild_FlashConduit_swf(self, request):
        #print "returning flash file"
        h = request.getHeader("user-agent")
        if h.count("MSIE"):
            fl = "FlashConduit.swf"
        else:
            fl = "FlashConduit.swf"
        return static.File(os.path.join(WOVEN_PATH, fl))

    def wchild_input_html(self, request):
        return BlankPage()


class BlankPage(resource.Resource):
    def render(self, request):
        return "<html>This space intentionally left blank</html>"


WController = Controller

def registerControllerForModel(controller, model):
    """
    Registers `controller' as an adapter of `model' for IController, and
    optionally registers it for IResource, if it implements it.

    @param controller: A class that implements L{interfaces.IController}, usually a
           L{Controller} subclass. Optionally it can implement
           L{resource.IResource}.
    @param model: Any class, but probably a L{twisted.web.woven.model.Model}
           subclass.
    """
    components.registerAdapter(controller, model, interfaces.IController)
    if resource.IResource.implementedBy(controller):
        components.registerAdapter(controller, model, resource.IResource)

