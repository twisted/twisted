"""A process that reads from stdin and out using Twisted."""

from twisted.python import log
log.startLogging(open("/tmp/process.log", "w"))

from twisted.internet import protocol, reactor, stdio


class Echo(protocol.Protocol):

    def connectionMade(self):
        print "connection made"
    
    def dataReceived(self, data):
        self.transport.write(data)

    def connectionLost(self):
        reactor.stop()

stdio.StandardIO(Echo())
reactor.run()
