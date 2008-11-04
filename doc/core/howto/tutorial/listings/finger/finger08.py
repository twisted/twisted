# Read username, output from non-empty factory, drop connections
# Use deferreds, to minimize synchronicity assumptions
from twisted.internet import protocol, reactor, defer
from twisted.protocols import basic

class FingerProtocol(basic.LineReceiver):
    def internalError(self, failure):
        return "Internal error in server"
    def reply(self, data):
        self.sendLine(data)
        self.transport.loseConnection()
    def lineReceived(self, user):
        d = self.factory.getUser(user)
        d.addErrback(self.internalError)
        d.addCallback(self.reply)

class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol
    def __init__(self, **kwargs):
        self.users = kwargs
    def getUser(self, user):
        return defer.succeed(self.users.get(user, "No such user"))

if __name__ == '__main__':
    reactor.listenTCP(1079, FingerFactory(moshez='Happy and well'))
    reactor.run()
