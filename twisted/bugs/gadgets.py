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
    <a href="create">Submit a new bug</a>
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

        for (id, name, email, assigned, date_create, date_mod, version, os, security, type, status, summary, description) in data:
            l.append( "<tr> <td> <a href='view_bug?bug_id=%d'>%s</a></td><td> %s </td> <td> %s</d><td> %s </td><td> %s </td></tr>\n" % (id, summary, type, status, assigned, date_mod) )
        l.append('</table>' )
        return l


class CreateNewForm(widgets.Form):
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
