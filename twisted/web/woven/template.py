
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
from twisted.internet import defer
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
    log.err(f)
    request.write(widgets.formatFailure(f))
    request.finish()


class INodeMutator(components.Interface):
    """A component that implements NodeMutator knows how to mutate
    DOM based on the instructions in the object it wraps.
    """
    def generate(self, request, node):
        """The generate method should do the work of mutating the DOM
        based on the object this adapter wraps.
        """
        pass


class NodeMutator:
    __implements__ = (INodeMutator, )
    def __init__(self, data):
        self.data = data


class NodeNodeMutator(NodeMutator):
    """A NodeNodeMutator replaces the node that is passed in to generate
    with the node it adapts.
    """ 
    def generate(self, request, node):
        if self.data is not node:
            if hasattr(self.d, 'importNode'):
                self.data = self.d.importNode(self.data, 1)
            parent = node.parentNode
            if parent:
                parent.replaceChild(self.data, node)
            else:
                print "WARNING: There was no parent for node %s; node not mutated" % node
        return self.data


class NoneNodeMutator(NodeMutator):
    def generate(self, request, node):
        child = self.d.createTextNode("None")
        node.parentNode.replaceChild(child, node)


class StringNodeMutator(NodeMutator):
    """A StringNodeMutator replaces the node that is passed in to generate
    with the string it adapts.
    """ 
    def generate(self, request, node):
        if self.data:
            try:
                child = minidom.parseString(html)
            except Exception, e:
                log.msg("Error parsing return value, probably invalid xml:", e)
                child = self.d.createTextNode(self.data)
        else:
            child = self.d.createTextNode(self.data)
        nodeMutator = NodeNodeMutator(child)
        nodeMutator.d = self.d
        return nodeMutator.generate(request, node)


class WebWidgetNodeMutator(NodeMutator):
    """A WebWidgetNodeMutator replaces the node that is passed in to generate
    with the result of generating the twisted.web.widget instance it adapts.
    """ 
    def generate(self, request, node):
        widget = self.data
        displayed = widget.display(request)
        try:
            html = string.join(displayed)
        except:
            pr = widgets.Presentation()
            pr.tmpl = displayed
            strList = pr.display(request)
            html = string.join(displayed)
        stringMutator = StringNodeMutator(html)
        return stringMutator.generate(request, node)


components.registerAdapter(NodeNodeMutator, minidom.Node, INodeMutator)        
components.registerAdapter(NoneNodeMutator, type(None), INodeMutator)        
components.registerAdapter(StringNodeMutator, type(""), INodeMutator)        
components.registerAdapter(WebWidgetNodeMutator, widgets.Widget, INodeMutator)        


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
            request.d = document
            self.setUp(request, document)
            # Don't let outstandingCallbacks get to 0 until the
            # entire tree has been recursed
            # If you don't do this, and any callback has already
            # completed by the time the dispatchResultCallback
            # is added in dispachResult, then sendPage will be
            # called prematurely within dispatchResultCallback
            # resulting in much gnashing of teeth.
            self.outstandingCallbacks += 1
            for node in document.childNodes:
                request.currentParent = node
                self.handleNode(request, node)
            self.outstandingCallbacks -= 1
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
        if not isinstance(result, defer.Deferred):
            adapter = components.getAdapter(result, INodeMutator, None, components.getAdapterClassWithInheritance)
            if adapter is None:
                raise NotImplementedError("Your factory method returned a %s instance, but there is no INodeMutator adapter registerred for that type." % type(result))
            adapter.d = self.d
            result = adapter.generate(request, node)
        if isinstance(result, defer.Deferred):
            self.outstandingCallbacks += 1
            result.addCallback(self.dispatchResultCallback, request, node)
            result.addErrback(renderFailure, request)
            # Got to wait until the callback comes in
        return result

    def recurseChildren(self, request, node):
        """
        If this node has children, handle them.
        """
        request.currentParent = node
        if not node: return
        if type(node.childNodes) == type(""): return
        if node.hasChildNodes():
            for child in node.childNodes:
                self.handleNode(request, child)

    def dispatchResultCallback(self, result, request, node):
        """
        Deal with a callback from a deferred, dispatching the result
        and recursing children.
        """
        self.outstandingCallbacks -= 1
        node = self.dispatchResult(request, node, result)
        self.recurseChildren(request, node)
        if not self.outstandingCallbacks:
            return self.sendPage(request)
    
    def handleNode(self, request, node):
        """
        Handle a single node by looking up a method for it, calling the method
        and dispatching the result.
        
        Also, handle all childNodes of this node using recursion.
        """
        if not hasattr(node, 'getAttribute'): # text node?
            return node
        
        viewName = node.getAttribute('view')
        if viewName:        
            method = getattr(self, "factory_" + viewName, None)
            if not method:
                nodeText = node.toxml()
                raise NotImplementedError, "You specified view name %s on a node, but no factory_%s method was found." % (viewName, viewName)
        
            result = method(request, node)
            node = self.dispatchResult(request, node, result)
        
        if not isinstance(node, defer.Deferred):
            self.recurseChildren(request, node)

    def sendPage(self, request):
        """
        Send the results of the DOM mutation to the browser.
        """
        page = str(self.d.toxml())
        request.write(page)
        request.finish()
        return page


##########################################
# Deprecation zone
# Wear a hard hat
##########################################


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
