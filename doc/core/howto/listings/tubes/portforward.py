from twisted.tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ClientEndpoint

def main(reactor):
    clientEndpoint = TCP4ClientEndpoint(reactor, 'localhost', 4321)
    serverEndpoint = TCP4ServerEndpoint(reactor, 6543)

    def forwardTubeFactory(listeningFount, listeningDrain):
        def outgoing(connectingFount, connectingDrain):
            listeningFount.flowTo(connectingDrain)
            connectingFount.flowTo(listeningDrain)
        clientEndpoint.connect(factoryFromFlow(outgoing))

    serverEndpoint.listen(factoryFromFlow(forwardTubeFactory))
    return Deferred()

from twisted.internet.task import react
react(main, [])
