from twisted.internet import default; default.install()
from twisted.internet import reactor, protocol, ptypro

class FakeTelnet(protocol.Protocol):
    commandToRun = ['/bin/sh'] # could have args too
    dirToRunIn = '/tmp'
    def connectionMade(self):
        print 'connection made'
        self.propro = ProcessProtocol(self)
        ptypro.Process(self.commandToRun[0],self.commandToRun,{},
            self.dirToRunIn, self.propro)
    def dataReceived(self, data):
        self.propro.transport.write(data)
    def conectionLost(self):
        print 'connection lost'
        self.propro.tranport.loseConnection()

class ProcessProtocol(protocol.Protocol):
    def __init__(self, pr):
        self.pr = pr
    def dataReceived(self, data):
        self.pr.transport.write(data)
    def processEnded(self):
        print 'protocol conection lost'
        self.pr.transport.loseConnection()

f = protocol.Factory()
f.protocol = FakeTelnet
reactor.listenTCP(5823, f)
reactor.run()
