# -*- python -*-
from twisted.application import service, internet
from nevow import appserver
from login import createResource

application = service.Application("login")
srv = internet.TCPServer(8081, appserver.NevowSite(createResource()))
srv.setServiceParent(application)
