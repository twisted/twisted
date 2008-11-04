# Read username, output from non-empty factory, drop connections
from twisted.internet import protocol, reactor
from twisted.protocols import basic

class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.sendLine(self.factory.getUser(user))
        self.transport.loseConnection()

class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol
    def __init__(self, **kwargs):
        self.users = kwargs
    def getUser(self, user):
        return self.users.get(user, "No such user")

if __name__ == '__main__':
    reactor.listenTCP(1079, FingerFactory(moshez='Happy and well'))
    reactor.run()
