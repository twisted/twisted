from twisted.web2 import server, http, resource, channel

class Toplevel(resource.Resource):
  addSlash = True
  def render(self, ctx):
	return http.Response(stream="Hello monkey!")

site = server.Site(Toplevel())

# Standard twisted application Boilerplate
from twisted.application import service, strports
application = service.Application("demoserver")
s = strports.service('tcp:8080', channel.HTTPFactory(site))
s.setServiceParent(application)
