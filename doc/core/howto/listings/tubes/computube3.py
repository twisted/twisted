
from twisted.tubes.protocol import factoryFromFlow

from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ServerEndpoint

from dataproc import dataProcessor

def mathFlow(fount, drain):
    fount.flowTo(dataProcessor()).flowTo(drain)

def main(reactor, port="4321"):
    endpoint = TCP4ServerEndpoint(reactor, int(port))
    endpoint.listen(factoryFromFlow(mathFlow))
    return Deferred()

from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
