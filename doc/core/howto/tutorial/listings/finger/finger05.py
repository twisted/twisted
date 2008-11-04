from twisted.internet import protocol, reactor
from twisted.protocols import basic

class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.sendLine("No such user")
        self.transport.loseConnection()

class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol

if __name__ == '__main__':
    reactor.listenTCP(1079, FingerFactory())
    reactor.run()
