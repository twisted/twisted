
import string

import insults

class RecvLineHandler:
    width = 80
    height = 24

    TABSTOP = 4

    ps = ('>>> ', '... ')
    pn = 0

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
            '\t': self.handle_TAB,
            proto.DELETE: self.handle_DELETE,
            proto.INSERT: self.handle_INSERT,
            proto.HOME: self.handle_HOME,
            proto.END: self.handle_END}

        self.initializeScreen()

    def initializeScreen(self):
        # Hmm, state sucks.  Oh well.
        # For now we will just take over the whole terminal.
        self.proto.reset()
        self.proto.write(self.ps[self.pn])
        self.setInsertMode()

    def setInsertMode(self):
        self.mode = 'insert'
        self.proto.setMode([insults.IRM])

    def setTypeoverMode(self):
        self.mode = 'typeover'
        self.proto.resetMode([insults.IRM])

    def terminalSize(self, width, height):
        # XXX - Clear the previous input line, redraw it at the new cursor position
        self.proto.reset()
        self.width = width
        self.height = height
        self.proto.write(self.ps[self.pn] + ''.join(self.lineBuffer))

    def unhandledControlSequence(self, seq):
        print "Don't know about", repr(seq)

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

    def handle_TAB(self):
        for i in range(self.TABSTOP - (len(self.lineBuffer) % self.TABSTOP)):
            self.keystrokeReceived(' ')

    def handle_LEFT(self):
        if self.lineBufferIndex > 0:
            self.lineBufferIndex -= 1
            self.proto.cursorBackward()

    def handle_RIGHT(self):
        if self.lineBufferIndex < len(self.lineBuffer):
            self.lineBufferIndex += 1
            self.proto.cursorForward()

    def handle_HOME(self):
        if self.lineBufferIndex:
            self.proto.cursorBackward(self.lineBufferIndex)
            self.lineBufferIndex = 0

    def handle_END(self):
        offset = len(self.lineBuffer) - self.lineBufferIndex
        if offset:
            self.proto.cursorForward(offset)
            self.lineBufferIndex = len(self.lineBuffer)

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
        self.proto.nextLine()
        self.lineReceived(line)

    def handle_INSERT(self):
        if self.mode == 'typeover':
            self.setInsertMode()
        else:
            self.setTypeoverMode()

    def lineReceived(self, line):
        pass

class HistoricRecvLineHandler(RecvLineHandler):
    def __init__(self, proto):
        RecvLineHandler.__init__(self, proto)

        self.historyLines = []
        self.historyPosition = 0

        self.keyHandlers.update({self.proto.UP_ARROW: self.handle_UP,
                                 self.proto.DOWN_ARROW: self.handle_DOWN})

    def handle_UP(self):
        if self.lineBuffer and self.historyPosition == len(self.historyLines):
            self.historyLines.append(self.lineBuffer)
        if self.historyPosition > 0:
            self.handle_HOME()
            self.proto.eraseToLineEnd()

            self.historyPosition -= 1
            self.lineBuffer = list(self.historyLines[self.historyPosition])
            self.proto.write(''.join(self.lineBuffer))
            self.lineBufferIndex = len(self.lineBuffer)

    def handle_DOWN(self):
        if self.historyPosition < len(self.historyLines) - 1:
            self.handle_HOME()
            self.proto.eraseToLineEnd()

            self.historyPosition += 1
            self.lineBuffer = list(self.historyLines[self.historyPosition])
            self.proto.write(''.join(self.lineBuffer))
            self.lineBufferIndex = len(self.lineBuffer)
        else:
            self.handle_HOME()
            self.proto.eraseToLineEnd()

            self.historyPosition = len(self.historyLines)
            self.lineBuffer = []
            self.lineBufferIndex = 0

    def handle_RETURN(self):
        if self.lineBuffer:
            self.historyLines.append(''.join(self.lineBuffer))
        self.historyPosition = len(self.historyLines)
        return RecvLineHandler.handle_RETURN(self)
