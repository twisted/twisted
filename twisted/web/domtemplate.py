
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

------------------------------------------------------

class Test(DOMTemplate):
    template = '''
<html><head><title>Foo</title></head><body>

<div class="Test">
This test node will be replaced
</div>

</body></html>
'''
    
    def getTemplateMethods(self):
        return [{'class': 'Test', 'method': self.test}]
    
    def test(self, request, node):
        '''
        The test method will be called with the request and the
        DOM node that the test method was associated with.
        '''
        # self.d has been bound to the main DOM "document" object 
        newNode = self.d.createTextNode("Testing, 1,2,3")
        
        # Replace the test node with our single new text node
        return newNode
"""

from cStringIO import StringIO
import string, os, stat, types
from xml.dom import minidom

from twisted.web.resource import Resource
from twisted.web import widgets # import Widget, Presentation
from twisted.web import domwidgets
from twisted.python.defer import Deferred
from twisted.python import failure
from twisted.internet import reactor
from twisted.python.mvc import View, IView, Controller
from twisted.python import log

from server import NOT_DONE_YET

class MethodLookup:
    def __init__(self):
        self._byid = {}
        self._byclass = {}
        self._bytag = {}

    def register(self, method=None, **kwargs):
        if not method:
           raise ValueError, "You must specify a method to register."
        if kwargs.has_key('id'):
            self._byid[kwargs['id']]=method
        if kwargs.has_key('class'):
            self._byclass[kwargs['class']]=method
        if kwargs.has_key('tag'):
            self._bytag[kwargs['tag']]=method

    def getMethodForNode(self, node):
        if not node.hasAttributes(): return
        id = node.getAttribute("id")
        if id:
            if self._byid.has_key(id):
                return self._byid[id]
        klass = node.getAttribute("class")
        if klass:
            if self._byclass.has_key(klass):
                return self._byclass[klass]
        if self._bytag.has_key(str(node.nodeName)):
            return self._bytag[str(node.nodeName)]
        return None

# If no widget/handler was found in the container controller or view, these modules will be searched.
import domhandlers, domwidgets

class DefaultHandler(Controller):
    def handle(self, request):
        """
        By default, we don't do anything
        """
        return (None, None)

    def setId(self, id):
        self.id = id


class DefaultWidget(domwidgets.Widget):
    def generateDOM(self, request, node):
        return node

    def setId(self, id):
        self.id = id


class DOMTemplate(Resource, View):
    """A resource that renders pages using DOM."""
    
    isLeaf = 1
    templateFile = ''
    template = ''
    _cachedTemplate = None

    def __init__(self, model = None):
        Resource.__init__(self)
        self.model = model
        self.templateMethods = MethodLookup()
        self.setTemplateMethods( self.getTemplateMethods() )
        
        self.outstandingCallbacks = 0

    def setTemplateMethods(self, tm):
        for m in tm:
            self.templateMethods.register(**m)

    def getTemplateMethods(self):
        """
        Override this to return a list of dictionaries specifying
        the tag attributes to associate with a method.
        
        e.g. to call the 'foo' method each time a tag with the class
        'bar' is encountered, use a dictionary like this:
        
        {'class': 'bar', 'method': self.foo}
        
        To call the "destroy" method each time the tag, class, or id
        "blink" is encountered, use a dictionary like this:
        
        {'class': 'blink', 'id': 'blink', 'tag': 'blink', 'method': self.destroy}
        """
        return []
        
    def render(self, request):        
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
        Override this if you want to have your subclass look up it's template
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
        # look up an object named by our template data member
        templateRef = request.pathRef().locate(self.templateFile)
        # Build a reference to the template on disk
        basePath = templateRef.parentRef().getObject().path
        templatePath = os.path.join(basePath, self.templateFile)
        # Check to see if there is an already compiled copy of it
        templateName = os.path.splitext(self.templateFile)[0]
        compiledTemplateName = templateName + '.pxp'
        compiledTemplatePath = os.path.join(basePath, compiledTemplateName)
        # No? Compile and save it
        if (not os.path.exists(compiledTemplatePath) or 
        os.stat(compiledTemplatePath)[stat.ST_MTIME] < os.stat(templatePath)[stat.ST_MTIME]):
            compiledTemplate = minidom.parse(templatePath)
            parent = templateRef.parentRef().getObject()
            parent.putChild(compiledTemplateName, compiledTemplate)
        else:
            from cPickle import Unpickler
            unp = Unpickler(open(compiledTemplatePath))
            compiledTemplate = unp.load()
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
            f = failure.Failure()
            request.write(widgets.formatFailure(f))
            request.finish()
    
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
            result.addCallbacks(self.callback, callbackArgs=(request, node))
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
        try:
            child = minidom.parseString(html)
        except Exception, e:
            print "damn, error parsing, probably invalid xml:", e
            child = self.d.createTextNode(html)
        return self.processNode(request, child, node)

    def processNode(self, request, newnode, oldnode):
        if newnode is not oldnode:
            if hasattr(self.d, 'importNode'):
                newnode = self.d.importNode(newnode, 1)
            oldnode.parentNode.replaceChild(newnode, oldnode)
        return newnode
    
    def handleNode(self, request, node):
        if not hasattr(node, 'getAttribute'): return node
        if node.nodeName and node.nodeName[0] == '#': return node
        
        controllerName = node.getAttribute('controller')
        viewName = node.getAttribute('view')
        id = node.getAttribute('model')
        if id is None: id = node.getAttribute('id')
        
        defaultHandlerFactory = lambda x: DefaultHandler(x)
        defaultWidgetFactory = lambda x: DefaultWidget(x)
        controllerFactory, viewFactory = (defaultHandlerFactory, defaultWidgetFactory)

        # Look up a handler
        if controllerName:
            if hasattr(self, 'controller'):
                controllerFactory = getattr(self.controller, 'factory_' + controllerName, defaultHandlerFactory)
            if controllerFactory is defaultHandlerFactory:
                controllerFactory = getattr(domhandlers, controllerName, defaultHandlerFactory)

        # Look up either a widget factory, or a dom-mutating method
        viewMethod = None
        viewMethod = self.templateMethods.getMethodForNode(node)
        if viewMethod:
            log.msg("getTemplateMethods is deprecated. Please switch from using class or id to using the model attribute, and prefix your methods with domview_*.")
        else:
            if viewName:
                viewFactory = getattr(self, 'factory_' + viewName, defaultWidgetFactory)
                if viewFactory is defaultWidgetFactory:
                    viewMethod = getattr(self, 'domview_' + viewName, None)
                    if viewMethod is None:
                        viewFactory = getattr(domwidgets, viewName, defaultWidgetFactory)

        controller = controllerFactory(self.model)
        view = viewFactory(self.model)

        controller.setView(view)
        controller.setId(id)
        # xxx refactor this into a widget interface and check to see if the object implements IWidget
        # the view may be a deferred; this is why this check is required
        if hasattr(view, 'setController'):
            view.setController(controller)
            view.setId(id)
            view.setNode(node)
        
        success, data = controller.handle(request)
        if success is not None:
            results = getattr(self, 'handlerResults', {})
            resultList = results.get(success, [])
            resultList.append((controller, data, node))
            results[success] = resultList
            setattr(self, 'handlerResults', results)

        if viewMethod is None:
            viewMethod = view.generateDOM
        self.mutateDOM(request, node, viewMethod)

    def mutateDOM(self, request, node, viewMethod):
        result = viewMethod(request, node)
        returnNode = self.dispatchResult(request, node, result)
        if not isinstance(returnNode, Deferred):
            node = returnNode
            self.recurseChildren(request, node)

    def sendPage(self, request):
        """
        Check to see if handlers recorded any errors before sending the page
        """
        # First, check to see if any results were recorded by handlers
        handlerResults = getattr(self, 'handlerResults', None)
        if handlerResults:
            # do something
            failures = handlerResults.get(0, None)
            if failures:
                stop = self.handleFailures(request, failures)
                if stop: return
            successes = handlerResults.get(1, None)
            if successes:
                self.handleSuccesses(request, successes)

        page = str(self.d.toprettyxml())
        request.write(page)
        request.finish()
        return page

    def handleFailures(self, request, failures):
        print "There were failures: ", failures
        return 0

    def handleSuccesses(self, request, successes):
        print "There were successes: ", successes
        pass

# DOMView is now deprecated since the functionality was merged into domtemplate
DOMView = DOMTemplate