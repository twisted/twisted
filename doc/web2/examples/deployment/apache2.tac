# You can run this .tac file directly with:
#    twistd -ny apache2.tac

from twisted.web2 import server, channel, static, vhost

# For example, serve the /tmp directory
toplevel = static.File("/tmp")
# Use the automatic uri rewriting based on apache2 headers
toplevel = vhost.AutoVHostURIRewrite(toplevel)
site = server.Site(toplevel)

# Start up the server
from twisted.application import service, strports
application = service.Application("demoserver")
s = strports.service('tcp:8538', channel.HTTPFactory(site))
s.setServiceParent(application)
