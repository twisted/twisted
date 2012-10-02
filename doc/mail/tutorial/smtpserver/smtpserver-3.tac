from twisted.application import service
from twisted.application import internet
from twisted.internet import protocol

application = service.Application("SMTP Server Tutorial")

smtpServerFactory = protocol.ServerFactory()
smtpServerFactory.protocol = protocol.Protocol

smtpServerService = internet.TCPServer(2025, smtpServerFactory)
smtpServerService.setServiceParent(application)
