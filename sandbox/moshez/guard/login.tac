from twisted.application import service, internet
from twisted.web import server
import login

application = service.Application("login")
i = internet.TCPServer(8081, server.Site(login.createResource()))
i.setServiceParent(application)
