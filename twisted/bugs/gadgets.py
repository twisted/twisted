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

"""Web interface to the bugs database."""

# system imports
import string

# twisted imports
from twisted.web import widgets


class BugsPage(widgets.WidgetPage):
    """Default look for bug pages."""
    
    template = '''
    <html>
    <head>
    <title>%%%%self.title%%%%</title>
    <base href="%%%%request.prePathURL()%%%%">
    </head>
    <body>
    <p>
    <a href=".">View all bugs</a> || <a href="create">Submit a new bug</a>
    </p>
    %%%%self.widget%%%%
    </body>
    </html>
    '''


class BugsGadget(widgets.StreamWidget, widgets.Gadget):
    """The main bugs gadget."""
    
    title = "List of Bugs"
    page = BugsPage
    
    def __init__(self, database):
        widgets.Gadget.__init__(self)
        self.database = database
        self.putWidget('create', CreateNewForm(self.database))
        self.putWidget('view_bug', ViewBug(self.database))
    
    def stream(self, write, request):
        """Display the intro list of bugs. This is only called if there is no URI.
        """
        write(self.database.getAllBugs().addCallback(self._cbBugs))

    def _cbBugs(self, data):
        l = []
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">'
                  '<tr bgcolor="#ff9900">'
                  '<td COLOR="#000000"><b> Summary </b> </td>'
                  '<td COLOR="#000000"><b> Type </b> </td>'
                  '<td COLOR="#000000"><b> Status </b> </td>'
                  '<td COLOR="#000000"><b> Assigned </b> </td>'
                  '<td COLOR="#000000"><b> Modification Date </b> </td>'
                  '</tr>\n' )

        for (id, summary, type, status, assigned, date_mod) in data:
            l.append( "<tr> <td> <a href='view_bug?bug_id=%d'>%s</a></td><td> %s </td> <td> %s</d><td> %s </td><td> %s </td></tr>\n" % (id, summary, type, status, assigned, date_mod) )
        l.append('</table>' )
        return l


class CreateNewForm(widgets.Form):
    """Form for creating new bugs."""
    
    title = "Create a new bug report:"
    
    def __init__(self, database):
        self.database = database

    def display(self, request):
        self.request = request
        typeNames = []
        for t in self.database.types:
            typeNames.append((t, string.capitalize(t)))
        self.formFields = [
            ['string', 'Name: ', 'name', ''],
            ['string', 'Email:', 'email', ''],
            ['string', 'Version:', 'version', ''],
            ['string', 'OS:', 'os', ''],
            ['checkbox', 'Security Related:', 'security', 0],
            ['menu', 'Type:', 'type', typeNames],
            ['string', 'Summary:', 'summary', ''],
            ['text', 'Description:', 'description', ''],
            ]
        
        return widgets.Form.display(self, self.request)
    
    def process(self, write, request, submit, name, email, version, os, security, type, summary, description):
        write(self.database.createBug(name, email, version, os, security, type, summary, description).addCallback(self._cbPosted))

    def _cbPosted(self, result):
        return ["Posted new bug."]


class ViewBug(widgets.Widget):
    """Display a bug."""
    
    def __init__(self, database):
        self.database = database
    
    def display(self, request):
        self.bug_id = int(request.args.get('bug_id',[0])[0])
        db = self.database
        return [db.getBug(self.bug_id).addCallback(self._cbBug), 
                db.getBugComments(self.bug_id).addCallback(self._cbComments)]
    
    def _cbBug(self, result):
        l = []
        for v in result[0]:
            l.append("%s<br>\n" % v)
        return l
    
    def _cbComments(self, result):
        l  = ["<h3>Comments</h3>\n"]
        for id, name, email, comment in result:
            l.append('<p><a href="mailto:%s">%s</a>:<br>\n'
                     '%s</p>\n' % (name, email, comment))
        return l
