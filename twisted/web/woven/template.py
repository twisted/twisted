
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

"""
DOMTemplate

Most templating systems provide commands that you embed 
in the HTML to repeat elements, include fragments from other 
files, etc. This works fairly well for simple constructs and people 
tend to get a false sense of simplicity from this. However, in my 
experience, as soon as the programmer wants to make the logic 
even slightly more complicated, the templating system must be 
bent and abused in ways it was never meant to be used.

The theory behind DOMTemplate is that Python code instead
of template syntax in the HTML should be used to manipulate
the structure of the HTML. DOMTemplate uses the DOM, a w3c 
standard tree-based representation of an HTML document that 
provides an API that allows you to traverse nodes in the tree, 
examine their attributes, move, add, and delete them. It is a 
fairly low level API, meaning it takes quite a bit of code to get 
a bit done, but it is standard -- learn the DOM once, you can 
use it from ActionScript, JavaScript, Java, C++, whatever.

A DOMTemplate subclass must do two things: indicate which
template it wants to use, and indicate which elements it is
interested in.

A short example::

   | class Test(DOMTemplate):
   |     template = '''
   | <html><head><title>Foo</title></head><body>
   | 
   | <div view="Test">
   | This test node will be replaced
   | </div>
   | 
   | </body></html>
   | '''
   |         
   |     def factory_test(self, request, node):
   |         '''
   |         The test method will be called with the request and the
   |         DOM node that the test method was associated with.
   |         '''
   |         # self.d has been bound to the main DOM "document" object 
   |         newNode = self.d.createTextNode("Testing, 1,2,3")
   |         
   |         # Replace the test node with our single new text node
   |         return newNode
"""

from cStringIO import StringIO
import string, os, sys, stat, types
from twisted.web import microdom as minidom

from twisted.python import components
from twisted.web import resource
from twisted.web.resource import Resource
from twisted.web import widgets # import Widget, Presentation
from twisted.internet.defer import Deferred
from twisted.python import failure
from twisted.internet import reactor, defer
from twisted.python.mvc import View, IView, Controller
from twisted.python import mvc
from twisted.python import log

from twisted.web.server import NOT_DONE_YET
STOP_RENDERING = 1
RESTART_RENDERING = 2


def renderFailure(ignored, request):
    f = failure.Failure()
    request.write(widgets.formatFailure(f))
    request.finish()


class DOMTemplate(Resource, View):
    """A resource that renders pages using DOM."""
    
    isLeaf = 1
    templateFile = ''
    templateDirectory = ''
    template = ''
    _cachedTemplate = None
    __implements__ = (Resource.__implements__, View.__implements__)

    def __init__(self, model = None):
        Resource.__init__(self)
        View.__init__(self, model)
        if self.controller is None:
            self.controller = self
        self.model = model
        
        self.outstandingCallbacks = 0
        
    def render(self, request):
        self.handlerResults = {1: [], 0: []}
        template = self.getTemplate(request)
        if template:
            self.d = minidom.parseString(template)
        else:
            if not self.templateFile:
                raise AttributeError, "%s does not define self.templateFile to operate on" % self.__class__
            self.d = self.lookupTemplate(request)
        # Schedule processing of the document for later...
        reactor.callLater(0, self.handleDocument, request, self.d)
        #self.handleNode(request, self.d)
        #return str(self.d.toxml())
        
        # So we can return NOT_DONE_YET
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
        if not self.templateDirectory:
            self.templateDirectory = os.path.split(sys.modules[self.__module__].__file__)[0]
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
        compiledTemplateName = templateName + '.pxp'
        compiledTemplatePath = os.path.join(self.templateDirectory, compiledTemplateName)
        # No? Compile and save it
        if (not os.path.exists(compiledTemplatePath) or 
        os.stat(compiledTemplatePath)[stat.ST_MTIME] < os.stat(templatePath)[stat.ST_MTIME]):
            compiledTemplate = minidom.parse(templatePath)
            from cPickle import dump
            dump(compiledTemplate, open(compiledTemplateName, 'wb'), 1)
#            parent = templateRef.parentRef().getObject()
#            parent.savePickleChild(compiledTemplateName, compiledTemplate)
        else:
            from cPickle import load
            compiledTemplate = load(open(compiledTemplatePath))
        return compiledTemplate

    def setUp(self, request, document):
        pass

    def handleDocument(self, request, document):
        """
        Handle the root node, and send the page if there are no
        outstanding callbacks when it returns.
        """
        try:
            self.setUp(request, document)
            for node in document.childNodes:
                self.handleNode(request, node)
            if not self.outstandingCallbacks:
                return self.sendPage(request)
        except:
            renderFailure(None, request)
    
    def dispatchResult(self, request, node, result):
        """
        Check a given result from handling a node and hand it to a process* 
        method which will convert the result into a node and insert it 
        into the DOM tree. Return the new node.
        """
        if isinstance(result, widgets.Widget):
            return self.processWidget(request, result, node)
        elif isinstance(result, minidom.Node):
            return self.processNode(request, result, node)
        elif isinstance(result, domwidgets.Widget):
            return self.processNode(request, result.generateDOM(request, node), node)
        elif isinstance(result, Deferred):
            self.outstandingCallbacks += 1
            result.addCallbacks(self.callback, renderFailure, callbackArgs=(request, node), errbackArgs=(request,))
            # Got to wait until the callback comes in
            return result
        elif isinstance(result, types.StringType):
            return self.processString(request, result, node)

    def recurseChildren(self, request, node):
        """
        If this node has children, handle them.
        """
        if not node: return
        if type(node.childNodes) == type(""): return
        if node.hasChildNodes():
            for child in node.childNodes:
                self.handleNode(request, child)

    def callback(self, result, request, node):
        """
        Deal with a callback from a deferred, dispatching the result
        and recursing children.
        """
        self.outstandingCallbacks -= 1
        node = self.dispatchResult(request, node, result)
        self.recurseChildren(request, node)
        if not self.outstandingCallbacks:
            return self.sendPage(request)

    def processWidget(self, request, widget, node):
        """
        Render a widget, and insert it in the current node.
        """
        displayed = widget.display(request)
        try:
            html = string.join(displayed)
        except:
            pr = widgets.Presentation()
            pr.tmpl = displayed
            strList = pr.display(request)
            html = string.join(displayed)
        return self.processString(request, html, node)

    def processString(self, request, html, node):
        if html:
            try:
                child = minidom.parseString(html)
            except Exception, e:
                log.msg("damn, error parsing, probably invalid xml:", e)
                child = self.d.createTextNode(html)
        else:
            child = self.d.createTextNode(html)
        return self.processNode(request, child, node)

    def processNode(self, request, newnode, oldnode):
        if newnode is not oldnode:
            if hasattr(self.d, 'importNode'):
                newnode = self.d.importNode(newnode, 1)
            if oldnode.parentNode:
                oldnode.parentNode.replaceChild(newnode, oldnode)
        return newnode
    
    def getNodeController(self, request, node):
        # Most specific
        controllerName = node.getAttribute('controller')
        
        # Look up a handler
        controllerFactory = DefaultHandler
        if controllerName:
            controllerFactory = getattr(self.controller, 'factory_' + controllerName, DefaultHandler)
            if controllerFactory is DefaultHandler:
                controllerFactory = getattr(dominput, controllerName, DefaultHandler)
        if controllerName and controllerFactory is DefaultHandler:
            nodeText = node.toxml()
            raise NotImplementedError, "You specified controller name %s on a node, but no factory_%s method was found." % (controllerName, controllerName)

        return controllerFactory(self.model)
    
    def getNodeView(self, request, node):
        result = None
        
        # Most specific
        viewName = node.getAttribute('view')

        # Look up either a widget factory, or a dom-mutating method
        defaultViewMethod = None
        view = DefaultWidget(self.model)
        viewMethod = view.generate
        defaultViewMethod = viewMethod
        if viewName:
            viewMethod = getattr(self, 'factory_' + viewName, defaultViewMethod)
            if viewMethod is defaultViewMethod:
                widget = getattr(domwidgets, viewName, None)
                if widget is not None:
                    view = widget(self.model)
                    viewMethod = view.generate
            else:
                # Check to see if the viewMethod returns a widget. (Use IWidget instead?)
                maybeWidget = viewMethod(request, node)
                if isinstance(maybeWidget, domwidgets.Widget):
                    view = maybeWidget
                    viewMethod = view.generate
                else:
                    result = maybeWidget
                    viewMethod = None
        
        if viewName and viewMethod is defaultViewMethod:
            del defaultViewMethod
            del viewMethod
            del view
            del result
            nodeText = node.toxml()
            raise NotImplementedError, "You specified view name %s on a node, but no factory_%s method was found." % (viewName, viewName)
        return view, viewMethod, result

    def handleNode(self, request, node):
        if not hasattr(node, 'getAttribute'): # text node?
            return node

        id = node.getAttribute('model')
        
        controller = self.getNodeController(request, node)
        view, viewMethod, result = self.getNodeView(request, node)

        submodel_prefix = node.getAttribute("_submodel_prefix")
        if submodel_prefix and id:
            submodel = "/".join([submodel_prefix, id])
        elif id:
            submodel = id
        elif submodel_prefix:
            submodel = submodel_prefix
        else:
            submodel = ""

        controller.setView(view)
        if not getattr(controller, 'submodel', None):
            controller.setSubmodel(submodel)
        # xxx refactor this into a widget interface and check to see if the object implements IWidget
        # the view may be a deferred; this is why this check is required
        if hasattr(view, 'setController'):
            view.setController(controller)
            view.setNode(node)
            if not getattr(view, 'submodel', None):
                view.setSubmodel(submodel)
        
        success, data = controller.handle(request)
        if success is not None:
            self.handlerResults[success].append((controller, data, node))

        if viewMethod is not None:
            result = viewMethod(request, node)
        returnNode = self.dispatchResult(request, node, result)
        if not isinstance(returnNode, Deferred):
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
        elif stop == RESTART_RENDERING:
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
        return RESTART_RENDERING

# DOMView is now deprecated since the functionality was merged into domtemplate
DOMView = DOMTemplate

# DOMController is now renamed woven.controller.WController
class DOMController(mvc.Controller, Resource):
    """
    A simple controller that automatically passes responsibility on to the view
    class registered for the model. You can override render to perform
    more advanced template lookup logic.
    """
    __implements__ = (mvc.Controller.__implements__, resource.IResource)
    
    def __init__(self, *args, **kwargs):
        log.msg("DeprecationWarning: DOMController is deprecated; it has been renamed twisted.web.woven.controller.WController.\n")
        mvc.Controller.__init__(self, *args, **kwargs)
        Resource.__init__(self)
    
    def setUp(self, request):
        pass

    def render(self, request):
        self.setUp(request)
        self.view = components.getAdapter(self.model, mvc.IView, None)
        self.view.setController(self)
        return self.view.render(request)

    def process(self, request, **kwargs):
        log.msg("Processing results: ", kwargs)
        return RESTART_RENDERING


# If no widget/handler was found in the container controller or view, these modules will be searched.
from twisted.web.woven import input
from twisted.web.woven import widgets as domwidgets

class DefaultHandler(Controller):
    def handle(self, request):
        """
        By default, we don't do anything
        """
        return (None, None)

    def setSubmodel(self, submodel):
        self.submodel = submodel


class DefaultWidget(domwidgets.Widget):
    def generate(self, request, node):
        return node

    def setSubmodel(self, submodel):
        self.submodel = submodel
