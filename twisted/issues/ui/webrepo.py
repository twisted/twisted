from twisted.web.woven import model as M, view as V, controller as C, widgets as W

class MethodModel(M.WModel):
    def getSubmodel(self, s):
        sm = getattr(self, "wmget_"+s)
        rv = sm()
        return rv

class MIssue(MethodModel):
    def __init__(self, issue):
        M.WModel.__init__(self)
        self.issue = issue

    def wmget_description(self):
        return self.issue.comments[0][1]

    def wmget_status(self):
        return self.issue.getStatusMessage()

    def wmget_number(self):
        return str(self.issue.number)

class MIssueRepository(MethodModel):
    def __init__(self, repository):
        M.WModel.__init__(self)
        self.repository = repository

    def wmget_issuelist(self):
        return map(MIssue, self.repository.issues.values())

from twisted.web.static import redirectTo, addSlash, File, Data
from twisted.web.resource import Resource, IResource
from twisted.web.error import NoResource
from twisted.python import components
import os
import issueconduit
class IssueSite(Resource):
    def __init__(self, repository, wordserv, templateDir):
        Resource.__init__(self)
        self.repository = repository
        self.wordserv = wordserv
        self.templateDir = templateDir

    def render(self, request):
        return redirectTo(addSlash(request), request)

    def makeView(self, model, name):
        v = V.View(model, name)
        v.templateDirectory = self.templateDir
        return v

    def child_index(self, request):
        return self.makeView(MIssueRepository(self.repository),
                             "webrepo_index.html")

    def child_tasks(self, request):
        return Data("Sorry check back later",
                    "text/plain")

    def child_issues(self, request):
        return self.makeView(MIssueRepository(self.repository),
                             "webrepo_issuelist.html")

    def child_conduit(self, request):
        return issueconduit.MWebConduit(self.wordserv, self.repository)

    def child_conduit_js(self, request):
        h = request.getHeader("user-agent")
        if h.count("MSIE"):
            pn = "conduit_msie.js"
        else:
            pn = "conduit_moz.js"
        return File(os.path.join(self.templateDir, pn))

    def getChild(self, path, request):
        if path == '': path = 'index'
        cm = getattr(self, "child_"+path, None)
        if cm:
            p = cm(request)
            adapter = components.getAdapter(p, IResource, None)
            if adapter:
                return adapter
        return NoResource()
