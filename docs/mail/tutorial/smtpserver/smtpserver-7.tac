import os

from zope.interface import implementer

from twisted.application import service

application = service.Application("SMTP Server Tutorial")

from twisted.application import internet
from twisted.internet import defer, protocol
from twisted.mail import smtp


@implementer(smtp.IMessage)
class FileMessage:
    def __init__(self, fileObj):
        self.fileObj = fileObj

    def lineReceived(self, line):
        self.fileObj.write(line + "\n")

    def eomReceived(self):
        self.fileObj.close()
        return defer.succeed(None)

    def connectionLost(self):
        self.fileObj.close()
        os.remove(self.fileObj.name)


@implementer(smtp.IMessageDelivery)
class TutorialDelivery:
    counter = 0

    def validateTo(self, user):
        fileName = "tutorial-smtp." + str(self.counter)
        self.counter += 1
        return lambda: FileMessage(open(fileName, "w"))

    def validateFrom(self, helo, origin):
        return origin

    def receivedHeader(self, helo, origin, recipients):
        return "Received: Tutorially."


class TutorialESMTPFactory(protocol.ServerFactory):
    protocol = smtp.ESMTP

    def buildProtocol(self, addr):
        p = self.protocol()
        p.delivery = TutorialDelivery()
        p.factory = self
        return p


smtpServerFactory = TutorialESMTPFactory()

smtpServerService = internet.TCPServer(2025, smtpServerFactory)
smtpServerService.setServiceParent(application)
