
from twisted.internet import protocol

import insults

# XXX - need to support scroll regions and scroll history
class TerminalBuffer(protocol.Protocol):
    width = 80
    height = 24

    fill = ' '

    def connectionMade(self):
        self.reset()

    def write(self, bytes):
        for b in bytes:
            self.insertAtCursor(b)

    def insertAtCursor(self, b):
        if b == '\r':
            self.x = 0
        elif b == '\n' or self.x >= self.width:
            self.x = 0
            self._scrollDown()
        if b != '\r' and b != '\n':
            self.lines[self.y][self.x] = b
            self.x += 1

    def _scrollDown(self):
        self.y += 1
        if self.y >= self.height:
            self.y -= 1
            del self.lines[0]
            self.lines.append(list(self.fill * self.width))

    def _scrollUp(self):
        self.y -= 1
        if self.y < 0:
            self.y = 0
            del self.lines[-1]
            self.lines.insert(0, list(self.fill * self.width))

    def cursorUp(self, n=1):
        self.y = max(0, self.y - n)

    def cursorDown(self, n=1):
        self.y = min(self.height - 1, self.y + n)

    def cursorBackward(self, n=1):
        self.x = max(0, self.x - n)

    def cursorForward(self, n=1):
        self.x = min(self.width, self.x + n)

    def cursorPosition(self, column, line):
        self.x = column
        self.y = line

    def cursorHome(self):
        self.x = self.home.x
        self.y = self.home.y

    def index(self):
        self._scrollDown()

    def reverseIndex(self):
        self._scrollUp()

    def nextLine(self):
        self.insertAtCursor('\n')

    def saveCursor(self):
        self._savedCursor = (self.x, self.y)

    def restoreCursor(self):
        self.x, self.y = self._savedCursor
        del self._savedCursor

    def setModes(self, modes):
        for m in modes:
            self.modes[m] = True

    def resetModes(self, modes):
        for m in modes:
            try:
                del self.modes[m]
            except KeyError:
                pass

    def applicationKeypadMode(self):
        self.keypadMode = 'app'

    def numericKeypadMode(self):
        self.keypadMode = 'num'

    def selectCharacterSet(self, charSet, which):
        self.charsets[which] = charSet

    def shiftIn(self):
        self.activeCharset = insults.G0

    def shiftOut(self):
        self.activeCharset = insults.G1

    def singleShift2(self):
        oldActiveCharset = self.activeCharset
        self.activeCharset = insults.G2
        f = self.insertAtCursor
        def insertAtCursor(b):
            f(b)
            del self.insertAtCursor
            self.activeCharset = oldActiveCharset
        self.insertAtCursor = insertAtCursor

    def singleShift3(self):
        oldActiveCharset = self.activeCharset
        self.activeCharset = insults.G3
        f = self.insertAtCursor
        def insertAtCursor(b):
            f(b)
            del self.insertAtCursor
            self.activeCharset = oldActiveCharset
        self.insertAtCursor = insertAtCursor

    def selectGraphicsRendition(self, *attributes):
        self._updateCharacterAttributes(attributes)

    def _updateCharacterAttributes(self, attrs):
        for a in attrs:
            print 'setting attr', a

    def eraseLine(self):
        self.lines[self.y] = list(self.fill * self.width)

    def eraseToLineEnd(self):
        width = self.width - self.x
        self.lines[self.y][self.x:] = list(self.fill * width)

    def eraseToLineBeginning(self):
        self.lines[self.y][:self.x + 1] = list(self.fill * (self.x + 1))

    def eraseDisplay(self):
        self.lines = [[self.fill] * self.width for i in xrange(self.height)]

    def eraseToDisplayEnd(self):
        self.eraseToLineEnd()
        height = self.height - self.y
        self.lines[self.y + 1:] = [list(self.fill * self.width) for i in range(height)]

    def eraseToDisplayBeginning(self):
        self.eraseToLineBeginning()
        self.lines[:self.y] = [list(self.fill * self.width) for i in range(self.y)]

    def deleteCharacter(self, n=1):
        del self.lines[self.y][self.x:self.x+n]
        self.lines[self.y].extend(self.fill * min(self.width - self.x, n))

    def insertLine(self, n=1):
        self.lines[self.y:self.y] = [list(self.fill * self.width) for i in range(n)]
        del self.lines[self.height:]

    def deleteLine(self, n=1):
        del self.lines[self.y:self.y+n]
        self.lines.extend([list(self.fill * self.width) for i in range(n)])

    def reportCursorPosition(self):
        return (self.x, self.y)

    def reset(self):
        self.home = insults.Vector(0, 0)
        self.lines = [[self.fill] * self.width for i in xrange(self.height)]
        self.modes = {}
        self.numericKeypad = 'app'
        self.activeCharset = insults.G0
        self.x = self.y = 0
        self.charsets = {
            insults.G0: insults.CS_US,
            insults.G1: insults.CS_US,
            insults.G2: insults.CS_ALTERNATE,
            insults.G3: insults.CS_ALTERNATE_SPECIAL}

    def __str__(self):
        return '\n'.join([''.join(L) for L in self.lines])
