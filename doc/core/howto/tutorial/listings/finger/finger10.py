# Read username, output from factory interfacing to web, drop connections
from twisted.internet import protocol, reactor
from twisted.protocols import basic
from twisted.web import client

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
    def __init__(self, prefix):
        self.prefix=prefix
    def getUser(self, user):
        return client.getPage(self.prefix+user)

if __name__ == '__main__':
    reactor.listenTCP(1079, FingerFactory(prefix='http://livejournal.com/~'))
    reactor.run()
