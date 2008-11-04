# Read username, output from factory interfacing to OS, drop connections
from twisted.internet import protocol, reactor, utils
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
    def getUser(self, user):
        return utils.getProcessOutput("finger", [user])

if __name__ == '__main__':
    reactor.listenTCP(1079, FingerFactory())
    reactor.run()
