
import insults
import recvline

from twisted.application import service

application = service.Application("Insults RecvLine Demo")

class DemoRecvLineHandler(recvline.HistoricRecvLineHandler):

    def promptLocation(self):
        return 0, self.height - 1

    def lineReceived(self, line):
        x, y = self.promptLocation()
        for n, line in enumerate(self.historyLines[:-5:-1]):
            self.proto.cursorPosition(x, y - n - 1)
            self.proto.eraseLine()
            self.proto.write(line)
        self.proto.cursorPosition(x, y)

from demolib import makeService
makeService({'handler': DemoRecvLineHandler,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
