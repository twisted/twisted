from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.python import log
from twisted.web.woven import interfaces


class FlashConduit(LineReceiver):
    delimiter = '\0'
    keepalive = 1
    def connectionMade(self):
        print "connection with flash movie opened"
        #self.transport.write("alert('helllllllo')\0")

    def connectionLost(self, reason):
        print "connection lost"
        #self.lp.unhookOutputConduit()

    def lineReceived(self, line):
        session = self.factory.site.getSession(line)
        self.lp = lp = session.getComponent(interfaces.IWovenLivePage)
        lp.hookupOutputConduit(self)

    def writeScript(self, data):
        #print "writing javascript", data
        self.transport.write(data + '\0')
    
    def finish(self):
        pass


class FlashConduitFactory(Factory):
    protocol = FlashConduit

    def __init__(self, site):
        self.site = site