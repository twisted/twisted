
import insults
import recvline

from twisted.application import service

application = service.Application("Insults RecvLine Demo")

class DemoRecvLineHandler(recvline.HistoricRecvLineHandler):
    def initializeScreen(self):
        self.proto.setMode([insults.SCROLL])
        self.proto.setScrollRegion(self.height - 5, self.height)
        recvline.HistoricRecvLineHandler.initializeScreen(self)

    def lineReceived(self, line):
        self.proto.write(line)
        self.proto.cursorPosition(0, self.height - 1)
        self.proto.index()

from demolib import makeService
makeService({'handler': DemoRecvLineHandler,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
