
import insults

from twisted.application import service

application = service.Application("Insults Demo App")

class DrawHandler(insults.TerminalListener):
    def __init__(self, proto):
        self.proto = proto
        self.proto.eraseDisplay()
        self.proto.resetMode([insults.IRM])

    def keystrokeReceived(self, keyID):
        if keyID == self.proto.UP_ARROW:
            self.proto.cursorDown()
        elif keyID == self.proto.DOWN_ARROW:
            self.proto.cursorUp()
        elif keyID == self.proto.LEFT_ARROW:
            self.proto.cursorBackward()
        elif keyID == self.proto.RIGHT_ARROW:
            self.proto.cursorForward()
        else:
            return
        self.proto.write('*')
        self.proto.cursorBackward()

from demolib import makeService
makeService({'handler': DrawHandler,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
