from twisted.web.woven import page, simpleguard, guard
from twisted.web import microdom, util

class BasePage(page.Page):
    """This is the page that you see if you're anonymous.
    """

    template = '''
    <html>
    <title>  </title>
    <body>
    <div model="error" />
    <div view="loginthing" />
    <div style="border: thin solid blue" model="common" />
    <div style="border: thin solid red" model="special" />
    </body>
    </html>
    '''

    def wmfactory_error(self, request):
        return ''

    def wmfactory_common(self, request):
        return "This is the common (anonymous) data."

    def wmfactory_special(self, request):
        return "No special data for you, Mr. Anonymous-pants."

    def wvupdate_loginthing(self, request, widget, model):
        microdom.lmx(widget.node).form(action=guard.INIT_PERSPECTIVE,
                                       model="form")

    def wmfactory_form(self, request):
        return guard.newLoginSignature.method(None)

class ErrorPage(BasePage):

    def __init__(self, formModel):
        BasePage.__init__(self)
        self.formModel = formModel

    def wmfactory_error(self, request):
        return 'Incorrect username/password'

    def wvupdate_loginthing(self, request, widget, model):
        microdom.lmx(widget.node).form(action="../"+guard.INIT_PERSPECTIVE,
                                       model="form")

    def wmfactory_form(self, request):
        return guard.newLoginSignature.method(self.formModel)

class LoggedIn(BasePage):

    def wvupdate_loginthing(self, request, widget, data):
        microdom.lmx(widget.node).a(href=
                                    guard.DESTROY_PERSPECTIVE).text("Log out.")

    def wmfactory_special(self, request):
        name = request.getComponent(simpleguard.Authenticated).name
        return "Welcome, %s" % name


def dumbRedirect(ignored):
    return util.Redirect(".")

def createResource():
    """Tying it all together.
    """
    from twisted.cred import checkers
    return simpleguard.guardResource(LoggedIn(),
                [checkers.InMemoryUsernamePasswordDatabaseDontUse(bob="bob")],
                nonauthenticated=BasePage(),
                callback=dumbRedirect, errback=ErrorPage)

if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.web import server
    reactor.listenTCP(9999, server.Site(createResource()))
    reactor.run()
