#!python

from twisted.internet import main
from twisted.spread import pb
from twisted.enterprise import adbapi
from twisted.web import widgets, server

import gadgets
import service

# Create Twisted application object
application = main.Application("posting board")

# Connect to a database.
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", "localhost:5432", database="sean")

# Create the service
forumService = service.ForumService("posting", application, dbpool)

# Create posting board object
gdgt = gadgets.ForumGadget(application, forumService)

# Accept incoming connections!
application.listenOn(8485, server.Site(gdgt))

# Done.
