#!python

from twisted.internet import app
from twisted.web import server, test, widgets
from twisted.manhole import webcoil, coil

# This is a stub to get services registered until we have a module
# discovery and loading interface on the web

from twisted.words import service
from twisted.manhole import service
from twisted.protocols import telnet

a = app.Application('twisted')
root = webcoil.ConfigRoot(a)
a.listenTCP(8080, server.Site(root))

application = a
