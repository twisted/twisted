from __future__ import generators
from twisted.internet import protocol

class GetMoreData:
    def __init__(self, amount=1024):
        self.amount = amount

class GeneratedProtocol(protocol.Protocol):
    def __init__(self):
        self.waitingFor = None
        self.sucker = self.suckData()
        self.buffer = ""

    def dataReceived(self, data):
        self.buffer += data
        if self.waitingFor is None:
            r = self.sucker.next()
            if isinstance(r, GetMoreData):
                self.waitingFor = r.amount
        else:
            if len(self.buffer) >= self.waitingFor:
                self.sucker.next()


class GetTenBytes(GeneratedProtocol):
    def suckData(self):
        print "sucking data"
        yield GetMoreData(10)
        print "got data"
        assert len(self.buffer) >= 10

f = protocol.Factory()
f.protocol = GetTenBytes
from twisted.internet import reactor
reactor.listenTCP(1025, f)
reactor.run()
