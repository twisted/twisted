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
