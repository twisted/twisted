
import insults

class Draw(insults.TerminalProtocol):
    cursors = list('!@#$%^&*()_+-=')

    def connectionMade(self):
        self.transport.eraseDisplay()
        self.transport.resetModes([insults.IRM])
        self.cursor = self.cursors[0]

    def keystrokeReceived(self, keyID):
        if keyID == self.transport.UP_ARROW:
            self.transport.cursorUp()
        elif keyID == self.transport.DOWN_ARROW:
            self.transport.cursorDown()
        elif keyID == self.transport.LEFT_ARROW:
            self.transport.cursorBackward()
        elif keyID == self.transport.RIGHT_ARROW:
            self.transport.cursorForward()
        elif keyID == ' ':
            self.cursor = self.cursors[(self.cursors.index(self.cursor) + 1) % len(self.cursors)]
        else:
            return
        self.transport.write(self.cursor)
        self.transport.cursorBackward()

