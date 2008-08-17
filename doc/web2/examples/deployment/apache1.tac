# You can run this .tac file directly with:
#    twistd -ny apache1.tac

from twisted.web2 import server, channel, static, vhost

# For example, serve the /tmp directory
toplevel = static.File("/tmp")
# Add the rewriter.
toplevel = vhost.VHostURIRewrite("http://myhostname.com/foo/", toplevel)
site = server.Site(toplevel)

# Start up the server
from twisted.application import service, strports
application = service.Application("demoserver")
s = strports.service('tcp:8538:interface=127.0.0.1', channel.HTTPFactory(site))
s.setServiceParent(application)
