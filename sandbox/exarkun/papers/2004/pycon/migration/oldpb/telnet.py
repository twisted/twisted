
from twisted.manhole import telnet

class ShellFactory(telnet.ShellFactory):
    def __init__(self, *a, **kw):
        telnet.ShellFactory.__init__(self, *a, **kw)
        self.protos = {}

    def buildProtocol(self, addr):
        p = telnet.ShellFactory.buildProtocol(self, addr)
        self.protos[str(addr)] = p
        return p
