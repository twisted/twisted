
import insults
import recvline

from twisted.application import service

application = service.Application("Insults RecvLine Demo")

class DemoRecvLine(recvline.HistoricRecvLine):
    def lineReceived(self, line):
        if line == "quit":
            self.transport.loseConnection()
        self.transport.write(line)
        self.transport.nextLine()
        self.transport.write(self.ps[self.pn])

from demolib import makeService
makeService({'protocolFactory': DemoRecvLine,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
