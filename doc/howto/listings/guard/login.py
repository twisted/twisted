from twisted.web.woven import simpleguard, page, guard
from twisted.web import resource, util, microdom
from twisted.cred import checkers, portal

class Authenticated(page.Page):

    template='<html>Hello <span model="name"/>!</html>'

    def wmfactory_name(self, request):
        return request.getComponent(simpleguard.Authenticated).name

class LoginPage(page.Page):
    """This is the page that is shown to non-logged in users."""

    isLeaf = True
    addSlash = 0
    template = '''<html>
    <head>
        <title>Login</title>
        <style type="text/css">
.formDescription, .formError {
    /* fixme - inherit */
    font-size: smaller;
    font-family: sans-serif;
    margin-bottom: 1em;
}

.formDescription {
    color: green;
}

.formError {
    color: red;
}
</style>
    </head>
    <body>
    <h1>Please Log In</h1>
    <div class="shell">
    <div class="loginform" view="loginform" />
    </div>

    </body>
</html>'''
    
    def __init__(self, formModel=None):
        page.Page.__init__(self)
        self.formModel = formModel

    def wvupdate_loginform(self, request, widget, model):
        microdom.lmx(widget.node).form(action=guard.INIT_PERSPECTIVE,
                                       model="form")

    def wmfactory_form(self, request):
        if self.formModel:
            return self.formModel
        else:
            return guard.newLoginSignature.method(None)


def callback(_):
    return util.Redirect(".")

def buildGuardedResource():
    return simpleguard.guardResource(
               Authenticated(),
               [checkers.InMemoryUsernamePasswordDatabaseDontUse(bob="12345")],
               nonauthenticated=LoginPage(),
               callback=callback, errback=LoginPage)
