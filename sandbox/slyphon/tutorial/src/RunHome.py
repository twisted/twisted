#!/usr/bin/env python2.3

from twisted.internet import app
from twisted.web import server
import HomePage


# We create a new twisted.web.server.Site by passing it
# an instance of the root page of our Woven application
site = server.Site(HomePage.HomePage())

# create a new application with name 'HomePage'
application = app.Application('HomePage')

# Set up port to listen on, and optionally the interface to listen on
application.listenTCP(7000, site)
#application.listenTCP(7000, site, interface="192.168.1.55")

# start the daemon process
application.run()

