"""

A demo app that can protect arbitrarily deep hierarchies.

Try e.g. http://localhost:8081/secret/stuff/stuff/stuff/
without authenticating first.

Requirements:

- Main page and some subpages do not need authentication.

- There are multiple subpages that require authentication.

- Pages that require authentication must show a login dialog, and
  after a succesful login act as if user was logged in already.

- The subpages requiring authentication may be deeply linked into from
  each other or the non-authenticating pages.

- The authentication should be shared amongst all the pages.

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
        if root is None:
            root=request.prePathURL()
        url = urlpath.URLPath.fromString(root)
        microdom.lmx(widget.node).form(
            action=str(url.sibling(guard.INIT_PERSPECTIVE)),
            model="form")

    def wmfactory_form(self, request):
        if self.formModel:
            return self.formModel
        else:
            return guard.newLoginSignature.method(None)

class Authenticated(page.Page):
    template='''<html>Hello <span model="name"/>! Look at all the <a href="stuff">stuff</a>, or go <a href="../">up</a></html>'''

    def wmfactory_name(self, request):
        return request.getComponent(simpleguard.Authenticated).name

    def wchild_stuff(self, request):
        return self

class Another(page.Page):
    template="""<html>This is another page requiring authentication. And there's  <a href="more">more</a>. Go <a href="../">up</a>.</html>"""

    def wchild_more(self, request):
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
        return self

    def render(self, request):
        request.getSession().setComponent(
            IRedirectAfterLogin,
            urlpath.URLPath.fromRequest(FullURLRequest(request))
            )
        return self.r.render(request)

class MainPage(page.Page):
    appRoot = True
    template='''\
<html>
<head>
<title>Main page</title>
</head>
<body>
<a href="secret">secret</a>,
<a href="secret/stuff/stuff/stuff">deep secret</a>,
<a href="another">another</a>,
<a href="another/more/more">another deep</a>,
<a href="../">up</a>.
</body>
</html>
'''

    def wchild_secret(self, request):
        a=request.getComponent(simpleguard.Authenticated)
        if not request.getComponent(simpleguard.Authenticated):
            return InfiniChild(LoginPage())
        return Authenticated()

    def wchild_another(self, request):
        a=request.getComponent(simpleguard.Authenticated)
        if not request.getComponent(simpleguard.Authenticated):
            return InfiniChild(LoginPage())
        return Another()

def createResource():
    return simpleguard.guardResource(
        MainPage(),
        [checkers.InMemoryUsernamePasswordDatabaseDontUse(test="test")],
        callback=callback)
