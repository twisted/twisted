
from twisted.internet.app import Application
from twisted.web.server import Site
from login import createResource

application = Application("login")
application.listenTCP(8081, Site(createResource()))
