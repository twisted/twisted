"""

A demo app that can protect arbitrarily deep hierarchies.

Try e.g. http://localhost:8081/secret/stuff/stuff/stuff/
without authenticating first.

"""

from twisted.web.woven import simpleguard, page, guard
from twisted.web import resource, util, microdom
from twisted.cred import checkers, portal
from twisted.python import urlpath

class LoginPage(page.Page):
    isLeaf = True
    """This is the page that is shown to non-logged in users."""

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
        root = request.getRootURL()
        assert root is not None, 'holy cow batman. TODO'
        url = urlpath.URLPath.fromString(root)
        microdom.lmx(widget.node).form(
            #action=str(url.parent().sibling(guard.INIT_PERSPECTIVE)),
            action=str(url.sibling(guard.INIT_PERSPECTIVE)),
            model="form")

    def wmfactory_form(self, request):
        if self.formModel:
            return self.formModel
        else:
            return guard.newLoginSignature.method(None)

class Authenticated(page.Page):
    isLeaf = 1
    template='<html>Hello <span model="name"/>! Look at all the <a href="stuff">stuff</a>.</html>'

    def wmfactory_name(self, request):
        return request.getComponent(simpleguard.Authenticated).name

    def wchild_stuff(self, request):
        return self

from twisted.python import components

class IRedirectAfterLogin(components.Interface):
    """The URLPath to which we will redirect after successful login.
    """

class Here(resource.Resource):
    def render(self, request):
        existing = request.getSession().getComponent(IRedirectAfterLogin, None)
        if existing is not None:
            request.redirect(str(existing))
            request.getSession().setComponent(IRedirectAfterLogin, None)
            return "<html></html>"
        else:
            return util.redirectTo('.', request)

def callback(model):
    return Here()

class FullURLRequest:
    def __init__(self, request):
        self.request = request

    def prePathURL(self):
        r = self.request
        prepath = r.prepath
        r.prepath = r.prepath + r.postpath
        rv = r.prePathURL()
        r.prepath = prepath
        return rv

class InfiniChild(resource.Resource):
    def __init__(self, r):
        resource.Resource.__init__(self)
        self.r = r

    def getChild(self, name, request):
        if request.getRootURL() is None:
            request.rememberRootURL()
        return self

    def render(self, request):
        request.getSession().setComponent(
            IRedirectAfterLogin,
            urlpath.URLPath.fromRequest(FullURLRequest(request))
            )
        return self.r.render(request)

class MainPage(page.Page):
    template='''\
<html>
<head>
<title>Main page</title>
</head>
<body>
<a href="secret">secret</a>,
</body>
</html>
'''
    foo=simpleguard.guardResource(
        Authenticated(),
        [checkers.InMemoryUsernamePasswordDatabaseDontUse(test="test")],
        nonauthenticated=InfiniChild(LoginPage()),
        callback=callback, errback=LoginPage)

    def wchild_secret(self, request):
        return self.foo

def createResource():
    return MainPage()
