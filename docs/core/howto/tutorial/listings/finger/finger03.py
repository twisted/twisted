from twisted.internet import protocol, reactor

class FingerProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.loseConnection()

class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol

reactor.listenTCP(1079, FingerFactory())
reactor.run()
