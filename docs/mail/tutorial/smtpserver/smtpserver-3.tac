from twisted.application import service

application = service.Application("SMTP Server Tutorial")

from twisted.application import internet
from twisted.internet import protocol

smtpServerFactory = protocol.ServerFactory()
smtpServerFactory.protocol = protocol.Protocol

smtpServerService = internet.TCPServer(2025, smtpServerFactory)
smtpServerService.setServiceParent(application)
