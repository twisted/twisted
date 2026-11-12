"""A process that reads from stdin and out using Twisted."""

import sys

from zope.interface import implementer

from twisted.internet import interfaces
from twisted.python import log

log.startLogging(sys.stderr)


from twisted.internet import protocol, reactor, stdio


@implementer(interfaces.IHalfCloseableProtocol)
class Echo(protocol.Protocol):
    def connectionMade(self):
        print("connection made")

    def dataReceived(self, data):
        self.transport.write(data)

    def readConnectionLost(self):
        print("readConnectionLost")
        self.transport.loseConnection()

    def writeConnectionLost(self):
        print("writeConnectionLost")

    def connectionLost(self, reason):
        print("connectionLost", reason)
        reactor.stop()


stdio.StandardIO(Echo())
reactor.run()
