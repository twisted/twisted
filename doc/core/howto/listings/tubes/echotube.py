from twisted.tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.defer import Deferred

def echoFlow(fount, drain):
    return fount.flowTo(drain)

def main(reactor, port="4321"):
    endpoint = TCP4ServerEndpoint(reactor, int(port))
    endpoint.listen(factoryFromFlow(echoFlow))
    return Deferred()

from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
