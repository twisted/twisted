# This shows an example of a bare-bones distributed web
# set up.
# The "master" and "slave" parts will usually be in different files
# -- they are here together only for brevity of illustration 

from twisted.internet import reactor, protocol
from twisted.web import server, distrib, static
from twisted.spread import pb

# The "master" server
site = server.Site(distrib.ResourceSubscription('unix', '.rp'))
reactor.listenTCP(19988, site)

# The "slave" server
fact = pb.PBServerFactory(distrib.ResourcePublisher(server.Site(static.File('static'))))

reactor.listenUNIX('./.rp', fact)
reactor.run()
