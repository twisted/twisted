
# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example OpenID reliant party.

Use this example with

  $ twistd -ny openidrp.tac

It will start a web server that listens on port 8080.
"""

from twisted.internet import reactor
from twisted.cred.portal import Portal
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web.openidchecker import OpenIDChecker, OpenIDCredentials
from twisted.web.openidchecker import OpenIDCallbackHandler
from twisted.application.service import Application
from twisted.application.internet import TCPServer

from openid.store.memstore import MemoryStore


class OpenIDPage(Resource):
    def __init__(self, portal):
        self.portal = portal
        Resource.__init__(self)

    def render_GET(self, request):
        return """
        <html><head><title>OpenID Example</title></head>
        <body>
        <form action="openid-start" method="post">
        <label for="openid">Enter OpenID</label>
        <input name="openid" />
        </form>
        </body>
        </html>
        """

class OpenIDAuthStart(Resource):
    def __init__(self, portal):
        self.portal = portal
        Resource.__init__(self)

    def render_POST(self, request):
        openid = request.args["openid"][0]
        credentials = OpenIDCredentials(request, openid, "UNUSED")
        # Calling login will basically take control of the request, so we
        # shouldn't do anything else with it.
        d = self.portal.login(credentials, None, None)
        d.addCallback(self.loggedIn)
        d.addErrback(self.badLogin)
        return NOT_DONE_YET

    def loggedIn(self, result):
        print "LOGGED IN!", result

    def badLogin(self, failure):
        print "COULDN'T LOG IN!", failure


class Realm(object):
    def requestAvatar(self, avatarId, mind, *interfaces):
        return interfaces[0], 3, lambda: None


store = MemoryStore()
checker = OpenIDChecker("http://localhost:8080/",
                        "http://localhost:8080/openid-callback",
                        store)
callbackHandler = OpenIDCallbackHandler(store, checker)

portal = Portal(Realm(), checkers=[checker])

root = Resource()
root.putChild("", OpenIDPage(portal))
root.putChild("openid-start", OpenIDAuthStart(portal))
root.putChild("openid-callback", callbackHandler)
site = Site(root)


application = Application("openid-reliant-party")
TCPServer(8080, site).setServiceParent(application)
