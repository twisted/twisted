from twisted.application import service
from twisted.application import internet
from twisted.internet import protocol
from twisted.mail import smtp

application = service.Application("SMTP Server Tutorial")

smtpServerFactory = protocol.ServerFactory()

smtpServerFactory.protocol = smtp.ESMTP

smtpServerService = internet.TCPServer(2025, smtpServerFactory)
smtpServerService.setServiceParent(application)
