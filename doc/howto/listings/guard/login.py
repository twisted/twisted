"""Root of forms."""

from twisted.web.woven import guard, page
from twisted.web import resource, static, util, microdom
from twisted.cred import checkers, portal, credentials


class User:
    """User info for current person."""
    
    def __init__(self, key):
        self.key = key


class RootPage(resource.Resource):
    """Root page users see when logged in."""
    
    def __init__(self, user):
        resource.Resource.__init__(self)
        self.user = user
        
    def render(self, request):
        return "Hello, %s!" % self.user.key


class UserRealm:
    """Realm for user pages."""
    
    def __init__(self, anonymousResource):
        self.service = service
        self.anonymousResource = anonymousResource
    
    def requestAvatar(self, avatarID, mind, interface):
        if avatarID == checkers.ANONYMOUS:
            return (resource.IResource, self.anonymousResource, lambda: None)
        else:
            user = User(avatarID)
            return (resource.IResource, RootPage(user), lambda: None)


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
        microdom.lmx(widget.node).form(action=guard.INIT_PERSPECTIVE, model="form")

    def wmfactory_form(self, request):
        if self.formModel:
            return self.formModel
        else:
            return guard.newLoginSignature.method(None)


def callback(_):
    return util.Redirect(".")

def buildGuardedResource():
    """Build guarded resource for the site."""
    myPortal = portal.Portal(UserRealm(LoginPage()))
    # hardcoded to single username/password - admin/password
    c = checkers.InMemoryUsernamePasswordDatabaseDontUse(admin="password")
    myPortal.registerChecker(c)
    myPortal.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
    un = guard.UsernamePasswordWrapper(myPortal, callback=callback, errback=LoginPage)
    return guard.SessionWrapper(un)
