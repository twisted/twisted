# -*- Python -*-

"""A sample web-based bug tracker.

http://localhost:8485/

Prerequisites:

 * install postgres server (apt-get install postgresql python-pgsql)
 * make yourself a user (su postgres -c adduser yourname)
 * create a database (createdb twisted)
 * set up bugs tables (psql --dbname twisted --file twisted/bugs/schema.sql)
"""

from twisted.internet import main
from twisted.spread import pb
from twisted.enterprise import adbapi, dbpassport
from twisted.web import widgets, server

from twisted.bugs import gadgets, bugsdb


# Connect to a database.
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="twisted")
auth = dbpassport.DatabaseAuthorizer(dbpool)

# Create Twisted application object
application = main.Application("bugs", authorizer_=auth)

# Create posting board object
gdgt = gadgets.BugsGadget(bugsdb.BugsDatabase(dbpool))

# Accept incoming connections!
s = server.Site(gdgt)
s.app = application
application.listenOn(8485, s)

# Done.
