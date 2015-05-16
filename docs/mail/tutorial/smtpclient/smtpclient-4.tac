from twisted.application import service

application = service.Application("SMTP Client Tutorial")

from twisted.application import internet
from twisted.internet import protocol

smtpClientFactory = protocol.ClientFactory()
smtpClientFactory.protocol = protocol.Protocol

smtpClientService = internet.TCPClient('localhost', 25, smtpClientFactory)
smtpClientService.setServiceParent(application)
