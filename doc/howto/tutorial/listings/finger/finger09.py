# Read username, output from factory interfacing to OS, drop connections
from twisted.internet import protocol, reactor, defer, utils
from twisted.protocols import basic
class FingerProtocol(basic.LineReceiver):
    def lineReceived(self, user):
        self.factory.getUser(user
        ).addErrback(lambda _: "Internal error in server"
        ).addCallback(lambda m:
                      (self.transport.write(m+"\r\n"),
                       self.transport.loseConnection()))
class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol
    def getUser(self, user):
        return utils.getProcessOutput("finger", [user])
reactor.listenTCP(1079, FingerFactory())
reactor.run()
