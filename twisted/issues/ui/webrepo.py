from twisted.web.woven import model as M, view as V, controller as C, \
     widgets as hoorj

class MIssue(M.WModel):
    def __init__(self, issue):
        M.WModel.__init__(self)
        self.issue = issue

class VIssue(hoorj.Widget):
    def setUp(self, request, node, data):
        i = self.getData().issue
        self.add(hoorj.Text("%s - %s - %s" % (i.number, i.comments[0][1],
                                              i.getStatusMessage())))

V.registerViewForModel(VIssue, MIssue)

class MIssueRepository(M.WModel):
    def __init__(self, repository):
        M.WModel.__init__(self)
        self.repository = repository

    def getSubmodel(self, s):
        sm = getattr(self, "model_"+s)
        return sm()

    def model_issuelist(self):
        return map(MIssue, self.repository.issues.values())

class VIssueRepository(V.WView):
    templateFile = "webrepo_template.html"

class CIssueRepository(C.WController):
    pass

V.registerViewForModel(VIssueRepository, MIssueRepository)
C.registerControllerForModel(CIssueRepository, MIssueRepository)
