# -*- test-case-name: twisted.web.test.test_woven -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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

import warnings

try:
    import cPickle as pickle
except ImportError:
    import pickle

import string, os, sys, stat, types
from twisted.web import microdom

from twisted.python import components
from twisted.web import resource, html
from twisted.web.resource import Resource
from twisted.web.woven import controller, utils, interfaces

from twisted.internet import defer
from twisted.python import failure
from twisted.internet import reactor, defer
from twisted.python import log
from zope.interface import implements, Interface

from twisted.web.server import NOT_DONE_YET
STOP_RENDERING = 1
RESTART_RENDERING = 2



class INodeMutator(Interface):
    """A component that implements NodeMutator knows how to mutate
    DOM based on the instructions in the object it wraps.
    """
    def generate(request, node):
        """The generate method should do the work of mutating the DOM
        based on the object this adapter wraps.
        """
        pass


class NodeMutator:
    implements(INodeMutator)
    def __init__(self, data):
        self.data = data

class NodeNodeMutator(NodeMutator):
    """A NodeNodeMutator replaces the node that is passed in to generate
    with the node it adapts.
    """
    def __init__(self, data):
        assert data is not None
        NodeMutator.__init__(self, data)

    def generate(self, request, node):
        if self.data is not node:
            parent = node.parentNode
            if parent:
                parent.replaceChild(self.data, node)
            else:
                log.msg("Warning: There was no parent for node %s; node not mutated." % node)
        return self.data


class NoneNodeMutator(NodeMutator):
    def generate(self, request, node):
        return node # do nothing
        child = request.d.createTextNode("None")
        node.parentNode.replaceChild(child, node)


class StringNodeMutator(NodeMutator):
    """A StringNodeMutator replaces the node that is passed in to generate
    with the string it adapts.
    """
    def generate(self, request, node):
        if self.data:
            try:
                child = microdom.parseString(self.data)
            except Exception, e:
                log.msg("Error parsing return value, probably invalid xml:", e)
                child = request.d.createTextNode(self.data)
        else:
            child = request.d.createTextNode(self.data)
        nodeMutator = NodeNodeMutator(child)
        return nodeMutator.generate(request, node)


components.registerAdapter(NodeNodeMutator, microdom.Node, INodeMutator)
components.registerAdapter(NoneNodeMutator, type(None), INodeMutator)
components.registerAdapter(StringNodeMutator, type(""), INodeMutator)


class DOMTemplate(Resource):
    """A resource that renders pages using DOM."""

    isLeaf = 1
    templateFile = ''
    templateDirectory = ''
    template = ''
    _cachedTemplate = None

    def __init__(self, templateFile = None):
        """
        @param templateFile: The name of a file containing a template.
        @type templateFile: String
        """
        Resource.__init__(self)
        if templateFile:
            self.templateFile = templateFile

        self.outstandingCallbacks = 0
        self.failed = 0

    def render(self, request):
        template = self.getTemplate(request)
        if template:
            self.d = microdom.parseString(template)
        else:
            if not self.templateFile:
                raise AttributeError, "%s does not define self.templateFile to operate on" % self.__class__
            self.d = self.lookupTemplate(request)
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
        # Check to see if there is an already compiled copy of it
        templateName = os.path.splitext(self.templateFile)[0]
        compiledTemplateName = '.' + templateName + '.pxp'
        compiledTemplatePath = os.path.join(self.templateDirectory, compiledTemplateName)
        # No? Compile and save it
        if (not os.path.exists(compiledTemplatePath) or
        os.stat(compiledTemplatePath)[stat.ST_MTIME] < os.stat(templatePath)[stat.ST_MTIME]):
            compiledTemplate = microdom.parse(templatePath)
            pickle.dump(compiledTemplate, open(compiledTemplatePath, 'wb'), 1)
        else:
            compiledTemplate = pickle.load(open(compiledTemplatePath, "rb"))
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
            self.renderFailure(None, request)

    def dispatchResult(self, request, node, result):
        """
        Check a given result from handling a node and hand it to a process*
        method which will convert the result into a node and insert it
        into the DOM tree. Return the new node.
        """
        if not isinstance(result, defer.Deferred):
            adapter = INodeMutator(result, None)
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

    def renderFailure(self, failure, request):
        try:
            xml = request.d.toxml()
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

##########################################
# Deprecation zone
# Wear a hard hat
##########################################


# DOMView is now deprecated since the functionality was merged into domtemplate
DOMView = DOMTemplate

# DOMController is now renamed woven.controller.Controller
class DOMController(controller.Controller, Resource):
    """
    A simple controller that automatically passes responsibility on to the view
    class registered for the model. You can override render to perform
    more advanced template lookup logic.
    """

    def __init__(self, *args, **kwargs):
        log.msg("DeprecationWarning: DOMController is deprecated; it has been renamed twisted.web.woven.controller.Controller.\n")
        controller.Controller.__init__(self, *args, **kwargs)
        Resource.__init__(self)

    def setUp(self, request):
        pass

    def render(self, request):
        self.setUp(request)
        self.view = interfaces.IView(self.model, None)
        self.view.setController(self)
        return self.view.render(request)

    def process(self, request, **kwargs):
        log.msg("Processing results: ", kwargs)
        return RESTART_RENDERING
