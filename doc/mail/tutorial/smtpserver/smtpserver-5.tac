from zope.interface import implements
from twisted.application import service
from twisted.application import internet
from twisted.internet import protocol, defer
from twisted.mail import smtp

application = service.Application("SMTP Server Tutorial")
smtpServerFactory = protocol.ServerFactory()

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

class TutorialESMTP(smtp.ESMTP):
    def validateFrom(self, helo, origin):
        return origin

    def validateTo(self, user):
        return ConsoleMessage

    def receivedHeader(self, helo, origin, recipients):
        return ('Received: from {}\n   to {}\n   by Tutorial Server'
                .format(origin, ", ".join([str(recipient) 
                                           for recipient in recipients])))
 

smtpServerFactory.protocol = TutorialESMTP

smtpServerService = internet.TCPServer(2025, smtpServerFactory)
smtpServerService.setServiceParent(application)
