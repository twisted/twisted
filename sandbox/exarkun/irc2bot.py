
from irc2 import AdvancedClient

from twisted.python import failure
from twisted.python import log
import sys
log.startLogging(sys.stdout)

class Client(AdvancedClient):
    nickname = 'irc2test'
    lineRate = 0.9

from twisted.internet import reactor, protocol

def main():
    proto = Client()
    cf = protocol.ClientFactory()
    cf.protocol = lambda: proto
    reactor.connectTCP('irc.freenode.net', 6667, cf)
    return proto
