# Read username, output from empty factory, drop connections
from twisted.internet import protocol, reactor
from twisted.protocols import basic

class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.sendLine(self.factory.getUser(user))
        self.transport.loseConnection()

class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol
    def getUser(self, user):
        return "No such user"

if __name__ == '__main__':
    reactor.listenTCP(1079, FingerFactory())
    reactor.run()
