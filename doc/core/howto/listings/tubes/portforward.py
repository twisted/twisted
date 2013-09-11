from twisted.tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ClientEndpoint

def main(reactor, host="localhost", port="4321", localport="6543"):
    clientEndpoint = TCP4ClientEndpoint(reactor, host, int(port))
    serverEndpoint = TCP4ServerEndpoint(reactor, int(localport))

    def forwardTubeFactory(listeningFount, listeningDrain):
        def outgoing(connectingFount, connectingDrain):
            listeningFount.flowTo(connectingDrain)
            connectingFount.flowTo(listeningDrain)
        clientEndpoint.connect(factoryFromFlow(outgoing))

    serverEndpoint.listen(factoryFromFlow(forwardTubeFactory))
    return Deferred()

from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
