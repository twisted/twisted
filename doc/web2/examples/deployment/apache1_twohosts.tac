# You can run this .tac file directly with:
#    twistd -ny apache1_twohosts.tac

from twisted.web2 import server, channel, resource, static, vhost

# For example, server the /tmp/foo directory
foo_toplevel = static.File("/tmp/foo")
# And the /tmp/bar directory
bar_toplevel = static.File("/tmp/bar")
# Add the rewriters:
foo_toplevel = vhost.VHostURIRewrite("http://foo.myhostname.com/", 
				  foo_toplevel)
bar_toplevel = vhost.VHostURIRewrite("http://bar.myhostname.com/",
				  bar_toplevel)

toplevel = resource.Resource()
toplevel.putChild('foo', foo_toplevel)
toplevel.putChild('bar', bar_toplevel)
site = server.Site(toplevel)

# Start up the server
from twisted.application import service, strports
application = service.Application("demoserver")
s = strports.service('tcp:8538:interface=127.0.0.1', channel.HTTPFactory(site))
s.setServiceParent(application)
