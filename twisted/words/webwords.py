
from twisted.web import html, server, resource, static

class AccountCreation(html.Interface):
    def content(self, request):
        if request.args.has_key("username"):
            u, p = request.args['username'][0], request.args['password'][0]
            print u, p
            svc = request.site.service
            part = svc.addParticipant(u,p)
            if part:
                return "Participant Added."
            else:
                return "Duplicate Name"
        else:
            return self.box(request,
                            "New Account",
                            self.form(request,
                                      [['string', "Username:", "username", ""],
                                       ['password', "Password:", "password", ""]])
                            )


class ParticipantInfo(html.Interface):
    def content(self, request):
        return "Sorry, this feature not complete yet."

class ParticipantsDirectory(html.Interface):
    def content(self, request):
        """Get HTML for a directory of participants.
        """
        svc = request.site.service
        keys =  svc.participants.keys()
        keys.sort()
        return self.runBox(request, "Directory",
                           html.linkList, map(
            lambda key, request=request: (request.childLink(key),key), keys))

    def getChild(self, path, request):
        """Get info for a particular participant.
        """
        return ParticipantInfo()

class AdminDir(html.Interface):
    def content(self, request):
        return html.linkList([
            ("users", "User Listing"),
            ("create", "Create Account")])

class WebWordsAdminSite(server.Site):
    def __init__(self, svc):
        res = resource.Resource()
        res.putChild("users", ParticipantsDirectory())
        res.putChild("create", AccountCreation())
        res.putChild("", AdminDir())
        server.Site.__init__(self, res)
        self.service = svc
        

