
import string

import insults

class RecvLineHandler:
    width = 80
    height = 24

    def __init__(self, proto, historyFilename=None):
        self.proto = proto
        self.historyFilename = historyFilename
        self._loadHistory()

        # Hmm, state sucks.  Oh well.
        # For now we will just take over the whole terminal.
        self.proto.eraseDisplay()
        self.proto.setMode([insults.IRM])
        self.proto.cursorPosition(2, self.height - 2)

        self.keyHandlers = {
            proto.UP_ARROW: self.handle_UP,
            proto.DOWN_ARROW: self.handle_DOWN,
            proto.LEFT_ARROW: self.handle_LEFT,
            proto.RIGHT_ARROW: self.handle_RIGHT,
            '\r': self.handle_RETURN,
            '\x7f': self.handle_BACKSPACE}

    def _loadHistory(self):
        if self.historyFilename is not None:
            self.history = list(file(self.historyFilename))
        else:
            self.history = []
        self.history.append('')
        self.historyPosition = len(self.history) + 1

    def terminalSize(self, width, height):
        self.width = width
        self.height = height
        self.proto.cursorPosition(2, self.height - 2)

    def unhandledControlSequence(self, seq):
        pass

    def setMode(self, modes):
        print 'Setting', modes

    def resetMode(self, modes):
        print 'Resetting', modes

    def keystrokeReceived(self, keyID):
        m = self.keyHandlers.get(keyID)
        if m is not None:
            m()
        elif keyID in string.printable:
            self.history[-1] += keyID
            self.proto.write(keyID)

    def displayLine(self, line):
        self.proto.cursorPosition(2, self.height - 2)
        self.proto.eraseLine()
        self.proto.write(line)

    def resetInputLine(self):
        self.history[-1] = self.history[self.historyPosition]
        self.displayLine(self.history[-1])

    def handle_UP(self):
        if self.historyPosition > 0:
            self.historyPosition -= 1
            self.resetInputLine()

    def handle_DOWN(self):
        if self.historyPosition < len(self.history) - 1:
            self.historyPosition += 1
            self.resetInputLine()

    def handle_LEFT(self):
        self.proto.cursorBackward()

    def handle_RIGHT(self):
        self.proto.cursorForward()

    def handle_BACKSPACE(self):
        if self.history[-1]:
            self.proto.cursorBackward()
            self.proto.deleteCharacter()
            self.history[-1] = self.history[-1][:-1]

    def handle_DELETE(self):
        self.proto.deleteCharacter()

    def handle_RETURN(self):
        self.history.append('')
        self.historyPosition = len(self.history)
        self.proto.eraseLine()
        self.proto.cursorPosition(2, self.height - 2)
