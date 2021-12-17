from cStringIO import StringIO

from twisted.internet import protocol, reactor, utils
from twisted.python import failure


class FortuneQuoter(protocol.Protocol):

    fortune = "/usr/games/fortune"

    def connectionMade(self):
        output = utils.getProcessOutput(self.fortune)
        output.addCallbacks(self.writeResponse, self.noResponse)

    def writeResponse(self, resp):
        self.transport.write(resp)
        self.transport.loseConnection()

    def noResponse(self, err):
        self.transport.loseConnection()


if __name__ == "__main__":
    f = protocol.Factory()
    f.protocol = FortuneQuoter
    reactor.listenTCP(10999, f)
    reactor.run()
