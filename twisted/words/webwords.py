
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

import time

#Twisted imports
from twisted.web import html, server, error, widgets
from twisted.internet import passport
from twisted.persisted import styles

#Sibling imports
import service

class AccountCreationWidget(widgets.Form, styles.Versioned):
    persistenceVersion = 1
    title = "Account Creation"
    formFields = [
        ['string','Username','username',''],
        ['password','Password','password',''],
        ]

    def __init__(self, service):
        self.service = service

    def upgradeToVersion1(self):
        #this object should get garbage collected..
        pass

    def process(self, write, request, **args):
        if args.has_key("username"):
            u,p = request.args['username'][0], request.args['password'][0]
            app = self.service.application
            ident = passport.Identity(u, app)
            ident.setPassword(p)
            app.authorizer.addIdentity(ident)
            part = self.service.createParticipant(u)
            part.setIdentity(ident)
            ident.addKeyForPerspective(part)
            if part:
                write("Participant Added.")
            else:
                write("Duplicate.")


class ParticipantInfoWidget(widgets.Widget):
    def __init__(self, name, svc):
        self.name = name
        self.title = "Info for Participant %s" % name
        self.service = svc
        self.part = svc.participants[name]

    def display(self, request):
        return ['''
        Name: %s<br>
        Currently in groups: %s<br>
        Current status: %s<br>
        ''' % (self.part.name,
               map(lambda x: x.name, self.part.groups),
               service.statuses[self.part.status])]


class ParticipantListWidget(widgets.Gadget, widgets.Widget, styles.Versioned):
    persistedVersion = 1
    def __init__(self, service):
        widgets.Gadget.__init__(self)
        self.service = service
        self.page = Page
        self.title = "Participant List"

    def upgradeToVersion1(self):
        #This object should get garbage collected..
        pass
        
    def display(self, request):
        """Get HTML for a directory of participants.
        """
        keys = self.service.participants.keys()
        keys.sort()
        return [html.linkList(map(lambda key, request=request:
                                  (key, key), keys))]

    def getWidget(self, name, request):
        """Get info for a particular participant.
        """
        if name in self.service.participants.keys():
            return ParticipantInfoWidget(name, self.service)
        else:
            return error.NoResource("That participant does not exist.")

class WordsGadget(widgets.Gadget, widgets.Widget, styles.Versioned):
    persistenceVersion = 1
    title = "WebWords Administration Interface"
    def __init__(self, svc):
        widgets.Gadget.__init__(self)
        self.section = ""
        self.putWidget("create", AccountCreationWidget(svc))
        self.putWidget("users", ParticipantListWidget(svc))
        self.page = Page

    def upgradeToVersion1(self):
        #This object should get garbage collected...
        pass


    def display(self, request):
        return [html.linkList([[request.childLink("create"),
                                "Create an Account"],
                               [request.childLink("users"),
                                "View the list of Participants"]])]
    
    

class Page(widgets.WidgetPage):
    box = widgets.TitleBox
    template = ('''
    <html><head><title>%%%%widget.title%%%%</title></head>
    <body bgcolor="#FFFFFF" text="#000000">
    <table><tr>'''
    #<td>%%%%widget.sidebar(widget.mode, widget.section)%%%%</td>
    '''
    <td>
    %%%%box(widget.title, widget)%%%%
    </td>
    </body></html>
    ''')


class WebWordsAdminSite(server.Site, styles.Versioned):
    persistenceVersion = 1
    def __init__(self, svc):
        res = WordsGadget(svc)
        server.Site.__init__(self, res)

    def upgradeToVersion1(self):
        self.__init__(self.service)
        del self.service

AccountCreation = AccountCreationWidget
ParticipantsDirectory = ParticipantListWidget
AdminDir = WordsGadget
