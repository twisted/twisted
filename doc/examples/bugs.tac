#!python

from twisted.internet import main
from twisted.spread import pb
from twisted.enterprise import adbapi, dbpassport
from twisted.web import widgets, server

from twisted.bugs import gadgets, bugsdb


# Connect to a database.
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="twisted")
auth = dbpassport.DatabaseAuthorizer(dbpool)

# Create Twisted application object
application = main.Application("bugs", authorizer=auth)

# Create posting board object
gdgt = gadgets.BugsGadget(bugsdb.BugsDatabase(dbpool))

# Accept incoming connections!
s = server.Site(gdgt)
s.app = application
application.listenOn(8485, s)

# Done.
