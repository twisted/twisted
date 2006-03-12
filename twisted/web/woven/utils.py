from __future__ import nested_scopes

from types import ClassType

from twisted.web import server
from twisted.web import util as webutil
from twisted.web.woven import interfaces
from twisted.python import failure, log, components
from zope.interface import implements

def renderFailure(fail, request):
    if not fail:
        fail = failure.Failure()
    log.err(fail)
    request.write(webutil.formatFailure(fail))
    #request.finish()


def doSendPage(self, d, request):
    page = str(d.toprettyxml())
    request.setHeader('content-length', str(len(page)))
    request.write(page)
    request.finish()
    return page


class Script:
    type="javascript1.2"
    def __init__(self, script):
        self.script = script


class WovenLivePage:
    implements(interfaces.IWovenLivePage)

    currentPage = None
    def __init__(self, session):
        self.session = session
        self.output = None
        self.input = None
        self.cached = []
        self.inputCache = []
    
    def getCurrentPage(self):
        """Return the current page object contained in this session.
        """
        return self.currentPage

    def setCurrentPage(self, page):
        """Set the current page object contained in this session.
        """
        self.currentPage = page

    def write(self, text):
        """Write "text" to the live page's persistent output conduit.
        If there is no conduit connected yet, save the text and write it
        as soon as the output conduit is connected.
        """
        if self.output is None:
            self.cached.append(text)
            print "CACHING", `self.cached`
        else:
            if isinstance(text, Script):
                if hasattr(self.output, 'writeScript'):
                    self.output.writeScript(text.script)
                    return
                text = '<script language="%s">%s</script>\r\n' % (text.type, text.script)
            print "WRITING", text
            if text[-1] != '\n':
                text += '\n'
            self.output.write(text)

    def sendScript(self, js):
        self.write(Script(js))
        if self.output is not None and not getattr(self.output, 'keepalive', None):
            print "## woot, teh connection was open"
            ## Close the connection; the javascript will have to open it again to get the next event.
            self.output.finish()
            self.output = None

    def hookupOutputConduit(self, request):
        """Hook up the given request as the output conduit for this
        session.
        """
        print "TOOT! WE HOOKED UP OUTPUT!", `self.cached`
        self.output = request
        for text in self.cached:
            self.write(text)
        if self.cached:
            self.cached = []
            if not getattr(self.output, 'keepalive', None):
                ## Close the connection; the javascript will have to open it again to get the next event.
                request.finish()
                self.output = None

    def unhookOutputConduit(self):
        self.output = None

    def hookupInputConduit(self, obj):
        """Hook up the given object as the input conduit for this
        session.
        """
        print "HOOKING UP", self.inputCache
        self.input = obj
        for text in self.inputCache:
            self.pushThroughInputConduit(text)
        self.inputCache = []
        print "DONE HOOKING", self.inputCache

    def pushThroughInputConduit(self, inp):
        """Push some text through the input conduit.
        """
        print "PUSHING INPUT", inp
        if self.input is None:
            self.inputCache.append(inp)
        else:
            self.input(inp)

class Stack:
    def __init__(self, stack=None):
        if stack is None:
            self.stack = []
        else:
            self.stack = stack
    
    def push(self, item):
        self.stack.insert(0, item)
    
    def pop(self):
    	if self.stack:
	        return self.stack.pop(0)
    
    def peek(self):
        for x in self.stack:
            if x is not None:
                return x
    
    def poke(self, item):
        self.stack[0] = item
    
    def clone(self):
        return Stack(self.stack[:])

    def __len__(self):
        return len(self.stack)
    
    def __getitem__(self, item):
        return self.stack[item]


class GetFunction:
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __call__(self, request, node, model, viewName):
        """Get a name from my namespace.
        """
        from twisted.web.woven import widgets
        if viewName == "None":
            return widgets.DefaultWidget(model)
    
        vc = getattr(self.namespace, viewName, None)
        # don't call modules and random crap in the namespace, only widgets
        if vc and isinstance(vc, (type, ClassType)) and issubclass(vc, widgets.Widget):
            return vc(model)


def createGetFunction(namespace):
    return GetFunction(namespace)


class SetId:
    def __init__(self, theId):
        self.theId = theId
    
    def __call__(self, request, wid, data):
        id = wid.attributes.get('id', None)
        if not id:
            wid.setAttribute('id', self.theId)
        else:
            top = wid
            while getattr(top, 'parent', None) is not None:
                top = top.parent
            if top.subviews.has_key(self.theId):
                del top.subviews[self.theId]
            top.subviews[id] = wid
            if wid.parent.subviews.has_key(self.theId):
                del wid.parent.subviews[self.theId]
            wid.parent.subviews[id] = wid


def createSetIdFunction(theId):
    return SetId(theId)



components.registerAdapter(WovenLivePage, server.Session, interfaces.IWovenLivePage)

