from twisted.tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.defer import Deferred

def echoFlow(fount, drain):
    return fount.flowTo(drain)

def main(reactor):
    endpoint = TCP4ServerEndpoint(reactor, 4321)
    endpoint.listen(factoryFromFlow(echoFlow))
    return Deferred()

from twisted.internet.task import react
react(main, [])
