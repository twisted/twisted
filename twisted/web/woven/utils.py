from __future__ import nested_scopes

from twisted.web import util as webutil
from twisted.web.woven import model, interfaces

from twisted.python import failure, log


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
    log.msg("Sending page!")
    #sess = request.getSession(IWovenLivePage)
    #if sess:
    #    sess.setCurrentPage(self)
    page = str(d.toxml())
    request.write(page)
    request.finish()
    return page


class WovenLivePage:
    currentPage = None
    __implements__ = interfaces.IWovenLivePage
    def getCurrentPage(self):
        """Return the current page object contained in this session.
        """
        return self.currentPage

    def setCurrentPage(self, page):
        """Set the current page object contained in this session.
        """
        self.currentPage = page


class Stack:
    def __init__(self, stack=None):
        if stack is None:
            self.stack = []
        else:
            self.stack = stack
    
    def push(self, item):
        self.stack.insert(0, item)
    
    def pop(self):
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
