
from recvline import RecvLineHandler
from insults import ServerProtocol
from telnet import TelnetBootstrapProtocol

from twisted.application import service, internet
from twisted.internet import protocol

class RecvLineProtocol(ServerProtocol):
    def connectionMade(self):
        self.handler = RecvLineHandler(self)

class RecvLineBootstrap(TelnetBootstrapProtocol):
    protocol = RecvLineProtocol

def makeService(args):
    f = protocol.ServerFactory()
    f.protocol = RecvLineBootstrap
    s = internet.TCPServer(args['port'], f)
    return s

application = service.Application("Insults RecvLine Demo")
makeService({'port': 6464}).setServiceParent(application)
