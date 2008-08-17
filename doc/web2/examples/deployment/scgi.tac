# You can run this .tac file directly with:
#    twistd -ny scgi.tac

from twisted.web2 import server, channel, static

# For example, serve the /tmp directory
toplevel = static.File("/tmp")
site = server.Site(toplevel)

# Start up the server
from twisted.application import service, strports
application = service.Application("demoserver")
s = strports.service('tcp:3000', channel.SCGIFactory(site))
s.setServiceParent(application)
