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
forumService = service.ForumService("posting", application, dbpool, "Forum Test Site")

# Create posting board object
gdgt = gadgets.GuardedForum(forumService)

# Accept incoming connections!
s = server.Site(gdgt)
s.app = application
application.listenOn(8485, s)


reg = gadgets.RegisterUser(application, forumService)
regsite = server.Site(reg)
application.listenOn(8488, regsite)


create = gadgets.NewForumForm(application, forumService)
csite = server.Site(create)
application.listenOn(8489, csite)

# Done.
