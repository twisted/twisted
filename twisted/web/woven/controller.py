
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

__version__ = "$Revision: 1.30 $"[11:-2]

import os
import cgi
import types

from twisted.python import log
from twisted.python import components
from twisted.web import resource, server, static
from twisted.web.woven import interfaces, utils
from twisted.web import woven

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

    __implements__ = (interfaces.IController, resource.IResource)
    setupStacks = 1
    controllerLibraries = []
    def __init__(self, m, inputhandlers=None, view=None, controllers=None):
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
        self._valid = {}
        self._invalid = {}
        self._process = {}

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
            if cm.func_code.co_argcount == 1 and not type(vm) == types.LambdaType:
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
        segment of the path.
        """
        if not name:
            method = "index"
        else:
            method = name
        f = getattr(self, "wchild_%s" % method, None)
        if f:
            return f(request)
        elif name == '':
            return self
        else:
            return resource.Resource.getChild(self, name, request)

    def render(self, request):
        """
        Trigger any inputhandlers that were passed in to this Page,
        then delegate to the View for traversing the DOM. Finally,
        call gatheredControllers to deal with any InputHandlers that
        were constructed from any controller= tags in the
        DOM. gatheredControllers will render the page to the browser
        when it is done.
        """
        # Handle any inputhandlers that were passed in to the controller first
        for ih in self._inputhandlers:
            ih._parent = self
            ih.handle(request)
        for key, value in self._valid.items():
            key.commit(request, None, value)
        self._valid = {}
        return self.renderView(request)

    def renderView(self, request):
        if self.view is None:
            self.setView(components.getAdapter(self.model, interfaces.IView, None))
            self.view.setController(self)
        return self.view.render(request, doneCallback=self.gatheredControllers)

    def gatheredControllers(self, v, d, request):
        process = {}
        for key, value in self._valid.items():
            key.commit(request, None, value)
            process[key.submodel] = value
        self.process(request, **process)
        #log.msg("Sending page!")
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
        return (None, None)

    def domChanged(self, request, node):
        parent = getattr(self, 'parent', None)
        if parent is not None:
            parent.domChanged(request, node)


WOVEN_PATH = os.path.split(woven.__file__)[0]

class LiveController(Controller):
    """A Controller that encapsulates logic that makes it possible for this
    page to be "Live". A live page can have it's content updated after the
    page has been sent to the browser, and can translate client-side
    javascript events into server-side events.
    """
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
            eventName = request.args['woven_clientSideEventName'][0]
            eventTarget = request.args['woven_clientSideEventTarget'][0]
            eventArgs = request.args.get('woven_clientSideEventArguments', [])
            #print "EVENT", eventName, eventTarget, eventArgs
            self.view = sess.getCurrentPage()
            request.d = self.view.d
            target = self.view.subviews[eventTarget]
            target.onEvent(request, eventName, *eventArgs)
            return '''<html>
    <body>
        %s event sent to %s with arguments %s.
    </body>
</html>''' % (eventName, cgi.escape(str(target)), eventArgs)

        # Unlink the current page in this user's session from MVC notifications
        page = sess.getCurrentPage()
        if page is not None:
            page.unlinkViews()
            sess.setCurrentPage(None)
        self.pageSession = None
        return Controller.render(self, request)

    def gatheredControllers(self, v, d, request):
        Controller.gatheredControllers(self, v, d, request)
        sess = request.getSession(interfaces.IWovenLivePage)
        #print "THIS PAGE IS GOING LIVE:", self
        self.pageSession = sess
        sess.setCurrentPage(self)

    def domChanged(self, request, node):
        print "DOM CHANGED"
        if self.pageSession is not None:
            nodeId = node.getAttribute('id')
            nodeXML = node.toxml()
            nodeXML = nodeXML.replace('\n', '')
            nodeXML = nodeXML.replace('\r', '')
            nodeXML = nodeXML.replace("'", "\\'")
            js = "top.woven_replaceElement('%s', '%s')" % (nodeId, nodeXML)
            self.pageSession.sendScript(js)

    def wchild_WebConduit2_js(self, request):
        print "returning js file"
        h = request.getHeader("user-agent")
        if h.count("MSIE"):
            fl = "WebConduit2_msie.js"
        else:
            fl = "WebConduit2_mozilla.js"

        return static.File(os.path.join(WOVEN_PATH, fl))

    def wchild_FlashConduit_swf(self, request):
        print "returning flash file"
        return static.File(os.path.join(WOVEN_PATH, "flashconduit.swf"))

    def wchild_input_html(self, request):
        return BlankPage()


class BlankPage(resource.Resource):
    def render(self, request):
        return "<html>nothing</html>"


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
    if components.implements(controller, resource.IResource):
        components.registerAdapter(controller, model, resource.IResource)

