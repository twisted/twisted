
"""
This example is meant to answer the frequently-asked question, 'How do I make a
website that only customizes part of a page depending on whether you're logge
in'?  It is a skeleton example of a woven application with login.
"""

from twisted.cred import checkers
from twisted.web.woven import page, guard, widgets
from twisted.web.microdom import lmx

from twisted.web.woven.form import FormFillerWidget


class BasePage(page.Page):
    """This is the page that you see if you're anonymous.
    """

    template = '''
    <html>
    <title>  </title>
    <body>
    <div view="loginthing" />
    <div style="border: thin solid blue" model="common" />
    <div style="border: thin solid red" model="special" />
    </body>
    </html>
    '''

    def wmfactory_common(self, request):
        return "This is the common (anonymous) data."

    def wmfactory_special(self, request):
        return "No special data for you, Mr. Anonymous-pants."

    def wvupdate_loginthing(self, request, widget, model):
        lmx(widget.node).form(action=guard.INIT_PERSPECTIVE, model="form")

    def wmfactory_form(self, request):
        return guard.newLoginSignature.method(None)

class LoggedIn(BasePage):
    def __init__(self, username):
        page.Page.__init__(self)
        self.username = username

    def wvupdate_loginthing(self, request, widget, data):
        lmx(widget.node).a(href=guard.DESTROY_PERSPECTIVE).text("Log out.")

    def wmfactory_special(self, request):
        return "Welcome, %s" % self.username

    def logout(self):
        print "%s's session timed out, or they logged out." %  (self.username)

# This is the authentication database part.

from twisted.cred.portal import IRealm
from twisted.web.resource import IResource

class MyRealm:
    """A simple implementor of cred's IRealm that gives us the LoggedIn page.
    """
    __implements__ = IRealm
    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource not in interfaces:
            raise NotImplementedError("I don't implement non-web login.")
        if avatarId:
            li = LoggedIn(avatarId)
            return (IResource, li, li.logout)
        else:
            lo = BasePage()
            return (IResource, lo, lambda : None)

from twisted.cred.portal import Portal
from twisted.cred.credentials import IAnonymous, IUsernamePassword
from twisted.cred.checkers import AllowAnonymousAccess, FilePasswordDB
from twisted.python.util import sibpath
from twisted.web.server import Site
from twisted.web.util import Redirect

def dumbRedirect(ignored):
    return Redirect(".")

def createResource():
    """Tying it all together.
    """
    # Create a Portal which acts as a gateway to our Realm.
    p = Portal(MyRealm())
    # Allow anonymous access.
    p.registerChecker(AllowAnonymousAccess(), IAnonymous)
    # Allow users registered in the password file.
    p.registerChecker(FilePasswordDB(sibpath(__file__, "passwords.txt")))
    # Create the resource.
    r = guard.SessionWrapper(guard.UsernamePasswordWrapper(p, callback=dumbRedirect))
    return r
