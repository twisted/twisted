from twisted.application import service

application = service.Application("SMTP Server Tutorial")

from twisted.application import internet
from twisted.internet import protocol

smtpServerFactory = protocol.ServerFactory()

from twisted.mail import smtp
smtpServerFactory.protocol = smtp.ESMTP

smtpServerService = internet.TCPServer(2025, smtpServerFactory)
smtpServerService.setServiceParent(application)
