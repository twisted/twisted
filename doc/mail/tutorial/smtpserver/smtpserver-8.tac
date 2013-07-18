from zope.interface import implements
from twisted.application import service
from twisted.application import internet
from twisted.internet import protocol, defer
from twisted.mail import smtp

application = service.Application("SMTP Server Tutorial")

class NullMessage(object):
    implements(smtp.IMessage)

    def lineReceived(self, line):
        pass

    def eomReceived(self):
        return defer.succeed(None)

    def connectionLost(self):
        pass

class ConsoleMessage(object):
    implements(smtp.IMessage)

    def __init__(self):
        self.lines=[]

    def lineReceived(self, line):
        self.lines.append(line)

    def eomReceived(self):
        print "New message received:"
        print "\n".join(self.lines)
        self.lines = None
        return defer.succeed(None)

    def connectionLost(self):
        self.lines = None

class TutorialDelivery(object):
    implements(smtp.IMessageDelivery)

    def __init__(self):
        self.to = []

    def validateFrom(self, helo, origin):
        return origin

    def validateTo(self, user):
        if self.to:
            self.to.append(user)
            return NullMessage
        else:
            self.to = [user]
            return ConsoleMessage

    def receivedHeader(self, helo, origin, recipients):
        return ('Received: from {}\n   to {}\n   by Tutorial Server'
                .format(origin, ", ".join([str(recipient) 
                                           for recipient in self.to])))
 
class TutorialDeliveryFactory(object):
    implements(smtp.IMessageDeliveryFactory)

    def getMessageDelivery(self):
        return TutorialDelivery()

class TutorialESMTPFactory(protocol.ServerFactory):
    protocol = smtp.ESMTP

    def buildProtocol(self, addr):
        p = self.protocol()
        p.deliveryFactory = TutorialDeliveryFactory()
        p.factory = self
        return p


smtpServerFactory = TutorialESMTPFactory()

smtpServerService = internet.TCPServer(2025, smtpServerFactory)
smtpServerService.setServiceParent(application)
