from twisted.internet import endpoints, protocol, reactor


class FingerProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.loseConnection()


class FingerFactory(protocol.ServerFactory):
    protocol = FingerProtocol


fingerEndpoint = endpoints.serverFromString(reactor, "tcp:1079")
fingerEndpoint.listen(FingerFactory())
reactor.run()
