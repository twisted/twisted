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
application = main.Application("forum", authorizer_=auth)

# Create the service
forumService = service.ForumService("posting", application, dbpool, "Forum Test Site")

# Create posting board object
gdgt = gadgets.ForumsGadget(forumService)

# Accept incoming connections!
s = server.Site(gdgt)
s.app = application
application.listenOn(8485, s)

# Done.




def done(data):
    print "Done update!", data
    
def got(data):
    for d in data:
        print d
        for k in d.__dict__.keys():
            print "   ", k, ": ", d.__dict__[k]

    for d in data:
        d.updateMe().addCallback(done).arm()

forumService.manager.loadObjectsFrom("twisted_perspectives",
                                     [("identity_name","varchar"),
                                      ("perspective_name","varchar")]).addCallback(got).arm()

#forumService.manager.loadObjectsFrom("metrics_sources",
#                                     [("source_id","int4")
#                                      ]).addCallback(got).arm()

