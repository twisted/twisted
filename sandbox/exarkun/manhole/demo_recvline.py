
from recvline import RecvLineHandler

from twisted.application import service, internet

application = service.Application("Insults RecvLine Demo")

class DemoRecvLineHandler(RecvLineHandler):
    def lineReceived(self, line):
        self.proto.saveCursor()
        self.proto.cursorUp()
        self.proto.insertLine()
        self.proto.write(line)
        self.proto.restoreCursor()

from demolib import makeService
makeService({'handler': DemoRecvLineHandler,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
