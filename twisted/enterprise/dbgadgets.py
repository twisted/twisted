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
"""Web interface for the Twisted db authentication system.

This now deprecated, as it is based on the old twisted.cred API
and uses a deprecated web widget system.

Has pages to:
    - show all the identities
    - show the perspectives for an identity
    - add a new identity
    - add a perspective for an identity
    - remove an identity
    - remove a perspective
    - change the password on an identity


top page: show identities and actions
    - remove
    - change password
    - create new
                    
for an identity: show perspectives and actions
    - remove
    - add

"""

import md5
import warnings

from twisted.web import widgets

warnings.warn("This is deprecated. You should be using Woven.",
              DeprecationWarning)

class IdentitiesGadget(widgets.Gadget, widgets.StreamWidget):
    title = "Database Identities"
    def __init__(self, authorizer):
        widgets.Gadget.__init__(self)
        self.authorizer = authorizer
        self.putWidget('perspectives',    PerspectivesGadget(authorizer))
        self.putWidget('newIdentity',     NewIdentityForm(authorizer))
        self.putWidget('newPerspective',  NewPerspectiveForm(authorizer))
        self.putWidget('removeIdentity',  RemoveIdentityForm(authorizer))
        self.putWidget('removePerspective',  RemovePerspectiveForm(authorizer))        
        self.putWidget('password',        ChangePasswordForm(authorizer))
        
    def display(self, request):
        """Display the list of identities
        """
        return [self.authorizer.getIdentities().addCallback(self.gotIdentities)]

    def gotIdentities(self, data):
        l = []
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000"><b> Identity </b> </td>' )
        l.append( '<td COLOR="#000000"><b> # of Perspectives </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Actions </b> </td>' )                                  
        l.append( '</tr>\n' )

        for (name, password, numPerspectives) in data:
            l.append( "<tr> <td> <a href='perspectives/?identityName=%s'>%s</a></td> " % (name, name) )
            l.append( "<td> %d </td>" % numPerspectives )
            l.append( "<td> <a href='/removeIdentity/?identityName=%s'>[remove]</a>" % name)
            l.append( "<a href='/password/?identityName=%s'>[password]</a> </td> </tr>\n" % ( name) )
            
        l.append("</table>")
        l.append("<br>[<a href='/newIdentity/'>Create an Identity</a>]<br> ")
        l.append( '<hr> <i> Twisted DB Authentication </i>' )        
        return l

class PerspectivesGadget(widgets.Gadget, widgets.Widget):
    title = " "
    def __init__(self, authorizer):
        widgets.Gadget.__init__(self)
        self.authorizer = authorizer

    def display(self, request):
        """Display the intro list of forums. This is only called if there is no URI.
        """
        self.identityName = request.args.get('identityName',[0])[0]                
        return [self.authorizer.getPerspectives(self.identityName).addCallback(self.gotPerspectives)]

    def gotPerspectives(self, data):
        l = []
        l.append('''
        <h3> Perspectives for Identity: %s </h3>
        <table cellpadding=4 cellspacing=1 border=0 width="95%">
        <tr bgcolor="#ff9900">
        <td COLOR="#000000"><b> Perspective Name </b> </td>
        <td COLOR="#000000"><b> Service </b> </td>
        <td COLOR="#000000"><b> Actions </b> </td>
        </tr>\n''' % self.identityName)

        for (iname, pname, sname) in data:
            l.append( "<tr> <td>%s</td> <td> %s </td>" % (pname, sname) )
            l.append( "<td> <a href='/removePerspective/?pname=%s&iname=%s'>[remove]</a></td></tr>\n" % (pname, self.identityName) )
            
        l.append("</table>")
        l.append("<br>[<a href='/newPerspective/?identityName=%s'>Add a Perspective</a>] " % self.identityName)
        l.append("[<a href='/password/?identityName=%s'>Change Password</a>]<br> " % self.identityName)
        l.append( '<hr> <i> Twisted DB Authentication </i>' )
        return l
        
class NewIdentityForm(widgets.Gadget, widgets.Form):
    title = "Create a New Identity:"

    def __init__(self, authorizer):
        self.authorizer = authorizer
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.request = request
        self.formFields = [
            ['string', 'Identity Name: ', 'name', ''],
            ['string', 'Password:',  'password',  '']
            ]
        
        return widgets.Form.display(self, self.request)
        
    
    def process(self, write, request, submit, name, password):
        m = md5.new()
        m.update(password)
        hashedPassword = m.digest()
        self.authorizer.addEmptyIdentity(name, hashedPassword)
        
        write("Created new identity '%s'.<hr>\n" % name)
        write("<a href='/'>Return to Main</a>")        


class NewPerspectiveForm(widgets.Gadget, widgets.Form):
    title = " "

    def __init__(self, authorizer):
        self.authorizer = authorizer
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.identityName = request.args.get('identityName',[0])[0]
        self.request = request
        return ["<h3> Add Perspective for Identity '%s'" % self.identityName,
                self.authorizer.getServices().addCallback(self.onServices)]

    def onServices(self, data):
        menuList = []
        for service, in data:
            menuList.append( (service, service) )
            
        self.formFields = [
            ['string', 'Perspective Name: ', 'name',    ''],
            ['menu',   'Service',            'service', menuList],
            ['hidden', '',                   'identityName', self.identityName]
            ]
        
        return widgets.Form.display(self, self.request)

    def process(self, write, request, submit, name, service, identityName):
        self.authorizer.addPerspective(self.identityName, name, service)
        
        write("Added perspective '%s' for '%s'.<hr>\n" % (self.identityName, name) )
        write("<a href='/'>Return to Main</a>")        


class ChangePasswordForm(widgets.Gadget, widgets.Form):
    title = " "

    def __init__(self, authorizer):
        self.authorizer = authorizer
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.identityName = request.args.get('identityName',[0])[0]
        self.formFields = [
            ['string', 'New Password: ', 'password',    ''],
            ['hidden', '',               'identityName', self.identityName]
            ]        
        return widgets.Form.display(self, request)

    def process(self, write, request, submit, password, identityName):
        m = md5.new()
        m.update(password)
        hashedPassword = m.digest()
        
        self.authorizer.changePassword(self.identityName, hashedPassword)
        
        write("Changed password for '%s'.<hr>\n" % (self.identityName) )
        write("<a href='/'>Return to Main</a>")        

class NewIdentityForm(widgets.Gadget, widgets.Form):
    title = "Create a New Identity:"

    def __init__(self, authorizer):
        self.authorizer = authorizer
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.request = request
        self.formFields = [
            ['string', 'Identity Name: ', 'name', ''],
            ['string', 'Password:',  'password',  '']
            ]
        
        return widgets.Form.display(self, self.request)
        
    def process(self, write, request, submit, name, password):
        m = md5.new()
        m.update(password)
        hashedPassword = m.digest()
        self.authorizer.addEmptyIdentity(name, hashedPassword)
        
        write("Created new identity '%s'.<hr>\n" % name)
        write("<a href='/'>Return to Main</a>")

class RemoveIdentityForm(widgets.Gadget, widgets.Form):
    title = "Confirm Removing Identity "

    def __init__(self, authorizer):
        self.authorizer = authorizer
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.identityName = request.args.get('identityName',[0])[0]
        self.request = request
        txt = "Remove Identity: %s" % self.identityName
        self.formFields = [
            ['string', '', 'txt', txt],
            ['hidden', '',  'identityName',  self.identityName]
            ]
        
        return widgets.Form.display(self, self.request)
        
    def process(self, write, request, submit, identityName, txt):
        self.authorizer.removeIdentity(self.identityName)
        write("Removed Identity %s.<hr>\n" % identityName)
        write("<a href='/'>Return to Main</a>")        

class RemovePerspectiveForm(widgets.Gadget, widgets.Form):
    title = "Confirm Removing Perspective"

    def __init__(self, authorizer):
        self.authorizer = authorizer
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.request = request
        self.pname = request.args.get('pname',[0])[0]
        self.iname = request.args.get('iname',[0])[0] 
        txt = "Remove Perspective %s for %s" % (self.pname, self.iname)
        
        self.formFields = [
            ['string', '', 'txt', txt ],
            ['hidden', '',  'iname',  self.iname],
            ['hidden', '',  'pname',  self.pname]            
            ]
        
        return widgets.Form.display(self, self.request)
        
    def process(self, write, request, submit, iname, pname, txt):
        self.authorizer.removePerspective(self.iname, self.pname)
        write("Removed %s for %s.<hr>\n" % (pname, iname) )
        write("<a href='/'>Return to Main</a>")        
