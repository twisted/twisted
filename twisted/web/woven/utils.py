from twisted.web import widgets as oldwidgets
from twisted.web.woven import model

from twisted.python import failure, log

def renderFailure(fail, request):
    if not fail:
        fail = failure.Failure()
    log.err(fail)
    request.write(oldwidgets.formatFailure(fail))
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
