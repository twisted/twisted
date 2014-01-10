from twisted.internet import protocol, reactor

class FingerProtocol(protocol.Protocol):
    pass

class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol

reactor.listenTCP(1079, FingerFactory())
reactor.run()
