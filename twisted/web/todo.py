"""I am a web-based interface to twisted.pim.todo which utilizes twisted.python.authenticator.
"""

#TR imports
import html


from twisted.protocols import http
from twisted.python import authenticator
from twisted.pim import todo


class WebTodoItem(html.Interface):
    def __init__(self, authenticator, todoitem):
        html.Interface.__init__(self)
        self.todoitem = todoitem
        self.authenticator = authenticator

    def checkAuth(self, request):
        try:
            self.authenticator.check(request.getUser(), request.getPassword())
        except authenticator.Unauthorized:
            request.setResponseCode(http.UNAUTHORIZED)
            request.setHeader('Www-Authenticate', 'basic realm="Twisted.Web"')
            return 0
        return 1


    def editMe(self, request):
        content = ""
        if not self.checkAuth(request):
            return ""
        content = content + "Edit me:"
        content = content + self.form(request, [
            ("string", "submitter", "submitter", self.todoitem.submitter),
            ("string", "assignee", "assignee", self.todoitem.assignee),
            ("string", "title", "title", self.todoitem.title),
            ("text", "description", "description", self.todoitem.description)],
            submit="OK", action="%s?change=1" % request.path)
        return content

    def changeItem(self, request):
        if not self.checkAuth(request):
            return "UNAUTHORIZED!!!"
        self.todoitem.updateItem(request.args["submitter"][0],
                                 request.args["assignee"][0],
                                 request.args["title"][0],
                                 request.args["description"][0])
        return "Item successfully updated!"

    def render(self, request):
        content = ""
        if request.args.has_key("change"):
            content = content + self.changeItem(request)
        if request.args.has_key("edit"):
            content = content + self.editMe(request)
        else:
            content = content + '<br><br><a href="%s?edit=1">Edit Me</a><br><br>' % request.path

        content = content + '<table border=1>' +\
                '<tr><td>Title</td><td>%s</td></tr>' % self.todoitem.title +\
                '<tr><td>Submitter</td><td>%s</td></tr>' % self.todoitem.submitter +\
                '<tr><td>Assignee</td><td>%s</td></tr>' % self.todoitem.assignee +\
                '<tr><td>Description</td><td>%s</td></tr>' % self.todoitem.description +\
                '</table>'

        return self.webpage(request, self.todoitem.title, self.box(request, self.todoitem.title, content))

class WebTodoList(html.Interface):
    def __init__(self, authenticator=authenticator.Authenticator({'admin': 'f00foo'})):
        html.Interface.__init__(self)
        self.authenticator = authenticator
        self.todolist = []

    def getChild(self, path, request):
        num = int(path)
        return WebTodoItem(self.authenticator, self.todolist[num])

    def checkAuth(self, request):
        try:
            self.authenticator.check(request.getUser(), request.getPassword())
        except authenticator.Unauthorized:
            request.setResponseCode(http.UNAUTHORIZED)
            request.setHeader('Www-Authenticate', 'basic realm="Twisted.Web"')
            return 0
        return 1

    def createNew(self, request):
        content = ""
        if not self.checkAuth(request):
            return "UNAUTHORIZED!!!"
        content = content + "Add a new item:"
        content = content + self.form(request, [
            ("string", "submitter", "submitter", "me"),
            ("string", "assignee", "assignee", "you"),
            ("string", "title", "title", ""),
            ("text", "description", "description", "")], submit="OK", action="%s?post=1" % request.path)
        return content

    def addItem(self, request):
        if not self.checkAuth(request):
            return "UNAUTHORIZED!!!"
        self.todolist.append(todo.TodoItem(request.args['submitter'][0],
                                           request.args['assignee'][0],
                                           request.args['title'][0],
                                           request.args['description'][0]))
        return "<br>Item succesfully added!<br>"

    def delItem(self, request, item):
        if not self.checkAuth(request):
            return "UNAUTHORIZED!"
        del self.todolist[item]
        return "item succesffully deleted!"

    def render(self, request):
        content = ""

        if request.args.has_key("newitem"):
            content = content + self.createNew(request)
        if request.args.has_key("post"):
            content = content + self.addItem(request)
        if request.args.has_key("del"):
            content = content + self.delItem(request, int(request.args["del"][0]))

        content = content + "<table border=1><tr><td>Title</td><td>Submitted by</td><td>assigned to</td><td>Delete?</td></tr>"
        for i in range(len(self.todolist)):
            todo = self.todolist[i]
            content = content + \
                      '<tr><td><a href="%s">%s</a></td><td>%s</td><td>%s</td><td><a href="%s?del=%d">del</a></td></tr>' \
                      % (request.childLink(str(i)), todo.title, todo.submitter, todo.assignee, request.path, i)
        content = content + "</table>"
        content = content + '<a href="%s?newitem=1">Create a new todo entry</a>' % request.path

        return self.webpage(request, "Todo list", 
                            self.box(request, "Todo List", content))

