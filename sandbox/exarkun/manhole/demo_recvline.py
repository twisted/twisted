
import insults
from recvline import RecvLineHandler

from twisted.application import service, internet

application = service.Application("Insults RecvLine Demo")

class DemoRecvLineHandler(RecvLineHandler):
    def initializeScreen(self):
        self.proto.setMode([insults.SCROLL])
        self.proto.setScrollRegion(self.height - 5, self.height)
        RecvLineHandler.initializeScreen(self)

    def lineReceived(self, line):
        self.proto.write(line)
        self.proto.cursorPosition(0, self.height)
        self.proto.index()

from demolib import makeService
makeService({'handler': DemoRecvLineHandler,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
