from __future__ import nested_scopes

from twisted.web import server
from twisted.web import util as webutil
from twisted.web.woven import model, interfaces
from twisted.python import failure, log, components


def renderFailure(fail, request):
    if not fail:
        fail = failure.Failure()
    log.err(fail)
    request.write(webutil.formatFailure(fail))
    #request.finish()

def _getModel(self):
    if not isinstance(self.model, model.Model): # see __class__.doc
         return self.model

    if self.submodel is None:
##         if hasattr(self.node, 'toxml'):
##             nodeText = self.node.toxml()
##         else:
##             widgetDict = self.__dict__
        return ""
##        raise NotImplementedError, "No model attribute was specified on the node."

    return self.model.lookupSubmodel(self.submodel)


def doSendPage(self, d, request):
    page = str(d.toxml())
    request.write(page)
    request.finish()
    return page


class Script:
    type="javascript1.2"
    def __init__(self, script):
        self.script = script


class WovenLivePage:
    currentPage = None
    __implements__ = interfaces.IWovenLivePage
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
            print "CACHING",
            self.cached.append(text)
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

    def hookupOutputConduit(self, request):
        """Hook up the given request as the output conduit for this
        session.
        """
        print "TOOT! WE HOOKED UP OUTPUT!"
        self.output = request
        for text in self.cached:
            self.write(text)
        self.cached = []
        # xxx start some sort of keepalive timer.

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

components.registerAdapter(WovenLivePage, server.Session, interfaces.IWovenLivePage)


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


def createGetFunction(namespace):
    def getFunction(request, node, model, viewName):
        """Get a name from the namespace in my closure.
        """
        if viewName == "None":
            from twisted.web.woven import widgets
            return widgets.DefaultWidget(model)
    
        vc = getattr(namespace, viewName, None)
        if vc:
            return vc(model)
    return getFunction

def createSetIdFunction(theId):
    def setId(request, wid, data):
        wid['id'] = theId
    return setId