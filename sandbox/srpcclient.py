from twisted.internet import protocol, reactor
from twisted.protocols import basic
import sys

class StupidRPCClient(basic.NetstringReceiver):
    def __init__(self, stuff):
        self.stuff = stuff

    def stringReceived(self, string):
        print 'S:', string
        if string in ('Success', 'Failure'):
            self.sendStrings()

    def connectionMade(self):
        self.sendStrings()

    def connectionLost(self, *args):
        reactor.stop()

    def sendStrings(self):
        if not self.stuff:
            return
        stuff = self.stuff.pop(0)
        print 'C:', stuff
        map(self.sendString, stuff)

stuff = sys.argv[1:]
stuff = [x.split(',') for x in stuff]
print stuff

f = protocol.ClientFactory()
f.protocol = lambda: StupidRPCClient(stuff)


reactor.connectTCP('localhost', 1025, f)
reactor.run()
