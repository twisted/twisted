
import string

import insults

class RecvLineHandler:
    width = 80
    height = 24

    def __init__(self, proto):
        self.proto = proto

        # A list containing the characters making up the current line
        self.lineBuffer = []

        # A zero-based (wtf else?) index into self.lineBuffer.
        # Indicates the current cursor position.
        self.lineBufferIndex = 0

        # A map of keyIDs to bound instance methods.
        self.keyHandlers = {
            proto.LEFT_ARROW: self.handle_LEFT,
            proto.RIGHT_ARROW: self.handle_RIGHT,
            '\r': self.handle_RETURN,
            '\x7f': self.handle_BACKSPACE,
            '\x04': self.handle_DELETE}

        self.initializeScreen()

    def initializeScreen(self):
        # Hmm, state sucks.  Oh well.
        # For now we will just take over the whole terminal.
        self.proto.eraseDisplay()
        self.proto.cursorPosition(0, self.height)
        self.setInsertMode()

    def setInsertMode(self):
        self.mode = 'insert'
        self.proto.setMode([insults.IRM])

    def setTypeoverMode(self):
        self.mode = 'typeover'
        self.proto.resetMode([insults.IRM])

    def terminalSize(self, width, height):
        # XXX - Clear the previous input line, redraw it at the new cursor position
        self.width = width
        self.height = height
        self.proto.cursorPosition(0, self.height)

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
            if self.mode == 'insert':
                self.lineBuffer.insert(self.lineBufferIndex, keyID)
            else:
                self.lineBuffer[self.lineBufferIndex:self.lineBufferIndex+1] = [keyID]
            self.lineBufferIndex += 1
            self.proto.write(keyID)
        else:
            print 'Received', repr(keyID)

    def handle_LEFT(self):
        if self.lineBufferIndex > 0:
            self.lineBufferIndex -= 1
            self.proto.cursorBackward()

    def handle_RIGHT(self):
        if self.lineBufferIndex < len(self.lineBuffer):
            self.lineBufferIndex += 1
            self.proto.cursorForward()

    def handle_BACKSPACE(self):
        if self.lineBufferIndex > 0:
            self.lineBufferIndex -= 1
            del self.lineBuffer[self.lineBufferIndex]
            self.proto.cursorBackward()
            self.proto.deleteCharacter()

    def handle_DELETE(self):
        if self.lineBufferIndex < len(self.lineBuffer) - 1:
            del self.lineBuffer[self.lineBufferIndex]
            self.proto.deleteCharacter()

    def handle_RETURN(self):
        line = ''.join(self.lineBuffer)
        self.lineBuffer = []
        self.lineBufferIndex = 0
        self.proto.eraseLine()
        self.proto.cursorPosition(0, self.height)

        self.lineReceived(line)

    def lineReceived(self, line):
        pass
