
from twisted.internet.app import Application
from login import createSite

application = Application("login")
application.listenTCP(8081, createSite())
