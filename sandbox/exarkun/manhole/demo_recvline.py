
import insults
import recvline

from twisted.application import service

application = service.Application("Insults RecvLine Demo")

class DemoRecvLineHandler(recvline.HistoricRecvLineHandler):
    def lineReceived(self, line):
        if line == "quit":
            self.proto.disconnect()
        self.proto.write(line)
        self.proto.nextLine()
        self.proto.write(self.ps[self.pn])

from demolib import makeService
makeService({'handler': DemoRecvLineHandler,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
