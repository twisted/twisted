"""A process that reads from stdin and out using Twisted."""

### Twisted Preamble
# This makes sure that users don't have to set up their environment
# specially in order to run these programs from bin/.
import sys, os, string
pos = string.find(os.path.abspath(sys.argv[0]), os.sep+'Twisted')
if pos != -1:
    sys.path.insert(0, os.path.abspath(sys.argv[0])[:pos+8])
sys.path.insert(0, os.curdir)
### end of preamble


from twisted.python import log
from zope.interface import implements
from twisted.internet import interfaces

log.startLogging(sys.stderr)

from twisted.internet import protocol, reactor, stdio


class Echo(protocol.Protocol):
    implements(interfaces.IHalfCloseableProtocol)
    
    def connectionMade(self):
        print "connection made"
    
    def dataReceived(self, data):
        self.transport.write(data)

    def readConnectionLost(self):
        print "readConnectionLost"
        self.transport.loseConnection()
    def writeConnectionLost(self):
        print "writeConnectionLost"
    
    def connectionLost(self, reason):
        print "connectionLost", reason
        reactor.stop()

stdio.StandardIO(Echo())
reactor.run()
