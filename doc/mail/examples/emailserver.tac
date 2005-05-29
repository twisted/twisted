
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this module directly with:
#    twistd -ny emailserver.tac


"""
A toy email server.
"""

from twisted.internet import defer
from twisted.protocols import smtp

class ConsoleMessageDelivery:
    __implements__ = (smtp.IMessageDelivery,)
    
    def receivedHeader(self, helo, origin, recipients):
        return "Received: ConsoleMessageDelivery"
    
    def validateFrom(self, helo, origin):
        # All addresses are accepted
        return origin
    
    def validateTo(self, user):
        # Only messages directed to the "console" user are accepted.
        if user.dest.local == "console":
            return lambda: ConsoleMessage()
        raise smtp.SMTPBadRcpt(user)

class ConsoleMessage:
    __implements__ = (smtp.IMessage,)
    
    def __init__(self):
        self.lines = []
    
    def lineReceived(self, line):
        self.lines.append(line)
    
    def eomReceived(self):
        print "New message received:"
        print "\n".join(self.lines)
        self.lines = None
        return defer.succeed(None)
    
    def connectionLost(self):
        # There was an error, throw away the stored lines
        self.lines = None

class ConsoleSMTPFactory(smtp.SMTPFactory):
    def __init__(self, *a, **kw):
        smtp.SMTPFactory.__init__(self, *a, **kw)
        self.delivery = ConsoleMessageDelivery()
    
    def buildProtocol(self, addr):
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.delivery = self.delivery
        return p

def main():
    from twisted.application import internet
    from twisted.application import service
    
    a = service.Application("Console SMTP Server")
    internet.TCPServer(2500, ConsoleSMTPFactory()).setServiceParent(a)
    
    return a

application = main()
