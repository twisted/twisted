# xmltresource.py

from cStringIO import StringIO
import string, os, stat

from twisted.web.resource import Resource
from twisted.web.widgets import Presentation

from xml.dom.minidom import *

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
        if u'id' in node.attributes.keys():
            id = str(node.attributes[u'id'].nodeValue)
            if self._byid.has_key(id):
                return self._byid[id]
        if u'class' in node.attributes.keys():
            klass = str(node.attributes[u'class'].nodeValue)
            if self._byclass.has_key(klass):
                return self._byclass[klass]
        if self._bytag.has_key(str(node.nodeName)):
            return self._bytag[str(node.nodeName)]
        return None

class DOMTemplate(Resource):
    templateFile = ''
    _cachedTemplate = None

    def __init__(self, model):
        Resource.__init__(self)
        self.model = model
        self.templateMethods = MethodLookup()
        self.setTemplateMethods( self.getTemplateMethods() )

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
        if not self.templateFile:
            raise AttributeError, "%s does not define self.templateFile to operate on" % self.__class__
        
        args = request.args
        if args.has_key('submit'):
            controller = self.controllerFactory(self.model, self)
            if controller:
                controller.submit(request, args)
            
        self.d = self.lookupTemplate(request)
        self.processNode(request, self.d)
        return str(self.d.toxml())
    
    def controllerFactory(self, model, view):
        """
        Override this if you want a controller to be instanciated when a form is
        submitted.
        """
        pass

    def lookupTemplate(self, request):
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
            compiledTemplate = parse(templatePath)
            parent = templateRef.parentRef().getObject()
            parent.putChild(compiledTemplateName, compiledTemplate)
        else:
            from cPickle import Unpickler
            unp = Unpickler(open(compiledTemplatePath))
            compiledTemplate = unp.load()
        return compiledTemplate
    
    def processNode(self, request, node):
        if node.nodeName and node.nodeName[0] != '#':
            nodeHandler = self.templateMethods.getMethodForNode(node)
            if nodeHandler:
                widget = apply(nodeHandler, (request, node))
                if widget:
                    self.processWidget(request, widget, node)
        if type(node.childNodes) == type(""): return
        for child in node.childNodes:
            self.processNode(request, child)

    def processWidget(self, request, widget, node):
        """
        Render a widget, and insert it in the current node.
        """
        displayed = widget.display(request)
        try:
            html = string.join(displayed)
        except:
            pr = Presentation()
            pr.tmpl = displayed
            strList = pr.display(request)
            html = string.join(displayed)
        try:
            node.childNodes = []
            child = parseString(html)
            for childNode in child.childNodes:
                try:
                    node.appendChild(childNode)
                except Exception, e:
                    # barfed on the node, skip it...
                    pass
        except Exception, e:
            print "damn, error parsing", e
            child = self.d.createTextNode(html)
            node.appendChild(child)

    def substitute(self, request, node, subs):
        """
        Look through the given node's children for strings, and
        attempt to do string substitution with the given parameter.
        """
        for child in node.childNodes:
            if child.nodeValue:
                child.replaceData(0, len(child.nodeValue), child.nodeValue % subs)
            self.substitute(request, child, subs)
            
    def locateNodes(self, nodeList, key, value):
        """
        Find subnodes in the given node where the given attribute
        as the given value.
        """
        returnList = []
        if not type(nodeList) is type([]) and not isinstance(nodeList, NodeList):
            return self.locateNodes(nodeList.childNodes, key, value)
        
        for childNode in nodeList:
            if not hasattr(childNode, 'getAttribute'):
                continue
            if str(childNode.getAttribute(key)) == value:
                returnList.append(childNode)
            returnList.extend(self.locateNodes(childNode, key, value))
        return returnList




