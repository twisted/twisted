# This shows an example of a bare-bones distributed web
# set up.
# The "master" and "slave" parts will usually be in different files
# -- they are here together only for brevity of illustatiojn 

from twisted.internet import app, protocol
from twisted.web import server, distrib, static
from twisted.spread import pb

application = app.Application("silly-web")

# The "master" server
site = server.Site(distrib.ResourceSubscription('unix', '.rp'))
application.listenTCP(19988, site)

# The "slaver" server
fact = pb.BrokerFactory(distrib.ResourcePublisher(server.Site(static.File('static'))))
application.listenTCP('./.rp', fact)
