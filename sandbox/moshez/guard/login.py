"""
A port of Tv's simplyguarded
"""

from twisted.web.woven import simpleguard, page, guard
from twisted.web import resource, util, microdom
from twisted.cred import checkers
from twisted.python import urlpath

class LoginPage(page.Page):
    isLeaf = True
    """This is the page that is shown to non-logged in users."""

    addSlash = 0
    templateFile = 'login.html'

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
    isLeaf = 1
    templateFile = 'authenticated.html'

    def wmfactory_name(self, request):
        return request.getComponent(simpleguard.Authenticated).name

    def wchild_stuff(self, request):
        return self

class Another(page.Page):
    isLeaf = 1
    templateFile='another.html'

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
            return ''
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
    templateFile = 'main.html'

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
