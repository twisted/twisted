from twisted.application import service

application = service.Application("SMTP Client Tutorial")

from twisted.application import internet
from twisted.internet import protocol
from twisted.mail import smtp

class SMTPClientFactory(protocol.ClientFactory):
    protocol = smtp.ESMTPClient

    def buildProtocol(self, addr):
        return self.protocol(secret=None, identity='example.com')

smtpClientFactory = SMTPClientFactory()

smtpClientService = internet.TCPClient('localhost', 25, smtpClientFactory)
smtpClientService.setServiceParent(application)
