from twisted.application import service

application = service.Application("SMTP Client Tutorial")

from twisted.application import internet
from twisted.internet import protocol

smtpClientFactory = protocol.ClientFactory()
smtpClientService = internet.TCPClient(None, None, smtpClientFactory)
smtpClientService.setServiceParent(application)
