
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


from twisted.web import html, server, resource, static

from twisted.internet import passport

class AccountCreation(html.Interface):

    def content(self, request):
        if request.args.has_key("username"):
            u, p = request.args['username'][0], request.args['password'][0]
            print u, p
            svc = request.site.service
            app = svc.application
            ident = passport.Identity(u, app)
            ident.setPassword(p)
            app.authorizer.addIdentity(ident)
            part = svc.addParticipant(u)
            part.setIdentity(ident)
            ident.addKeyForPerspective(part)
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
        

