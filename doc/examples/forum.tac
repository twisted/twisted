#!python

from twisted.internet import main
from twisted.spread import pb
from twisted.enterprise import adbapi, dbpassport
from twisted.web import widgets, server

from twisted.forum import gadgets, service


# Connect to a database.
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", "localhost:5432", database="sean")
auth = dbpassport.DatabaseAuthorizer(dbpool)

# Create Twisted application object
application = main.Application("forum", authorizer=auth)

# Create the service
forumService = service.ForumService("posting", application, dbpool)

# Create posting board object
gdgt = gadgets.ForumsGadget(application, forumService)

# Accept incoming connections!
application.listenOn(8485, server.Site(gdgt))

# Done.
