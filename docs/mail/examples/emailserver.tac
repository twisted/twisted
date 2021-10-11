# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this module directly with:
#    twistd -ny emailserver.tac

"""
A toy email server.
"""

from zope.interface import implementer

from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm, Portal
from twisted.internet import defer
from twisted.mail import smtp
from twisted.mail.imap4 import LOGINCredentials, PLAINCredentials


@implementer(smtp.IMessageDelivery)
class ConsoleMessageDelivery:
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


@implementer(smtp.IMessage)
class ConsoleMessage:
    def __init__(self):
        self.lines = []

    def lineReceived(self, line):
        self.lines.append(line)

    def eomReceived(self):
        print("New message received:")
        print("\n".join(self.lines))
        self.lines = None
        return defer.succeed(None)

    def connectionLost(self):
        # There was an error, throw away the stored lines
        self.lines = None


class ConsoleSMTPFactory(smtp.SMTPFactory):
    protocol = smtp.ESMTP

    def __init__(self, *a, **kw):
        smtp.SMTPFactory.__init__(self, *a, **kw)
        self.delivery = ConsoleMessageDelivery()

    def buildProtocol(self, addr):
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.delivery = self.delivery
        p.challengers = {"LOGIN": LOGINCredentials, "PLAIN": PLAINCredentials}
        return p


@implementer(IRealm)
class SimpleRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        if smtp.IMessageDelivery in interfaces:
            return smtp.IMessageDelivery, ConsoleMessageDelivery(), lambda: None
        raise NotImplementedError()


def main():
    from twisted.application import internet, service

    portal = Portal(SimpleRealm())
    checker = InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser("guest", "password")
    portal.registerChecker(checker)

    a = service.Application("Console SMTP Server")
    internet.TCPServer(2500, ConsoleSMTPFactory(portal)).setServiceParent(a)

    return a


application = main()
