
from helper import TerminalBuffer
from insults import ServerProtocol, ClientProtocol

from twisted.trial import unittest

WIDTH = 80
HEIGHT = 24

class BufferTestCase(unittest.TestCase):
    def setUp(self):
        self.term = TerminalBuffer()
        self.term.connectionMade()

    def testInitialState(self):
        self.assertEquals(self.term.width, WIDTH)
        self.assertEquals(self.term.height, HEIGHT)
        self.assertEquals(str(self.term),
                          '\n'.join([' ' * WIDTH for i in xrange(HEIGHT)]))
        self.assertEquals(self.term.reportCursorPosition(), (0, 0))

    def testCursorDown(self):
        self.term.cursorDown(3)
        self.assertEquals(self.term.reportCursorPosition(), (0, 3))
        self.term.cursorDown()
        self.assertEquals(self.term.reportCursorPosition(), (0, 4))
        self.term.cursorDown(HEIGHT)
        self.assertEquals(self.term.reportCursorPosition(), (0, HEIGHT - 1))

    def testCursorUp(self):
        self.term.cursorUp(5)
        self.assertEquals(self.term.reportCursorPosition(), (0, 0))

        self.term.cursorDown(20)
        self.term.cursorUp(1)
        self.assertEquals(self.term.reportCursorPosition(), (0, 19))

        self.term.cursorUp(19)
        self.assertEquals(self.term.reportCursorPosition(), (0, 0))

    def testCursorForward(self):
        self.term.cursorForward(2)
        self.assertEquals(self.term.reportCursorPosition(), (2, 0))
        self.term.cursorForward(2)
        self.assertEquals(self.term.reportCursorPosition(), (4, 0))
        self.term.cursorForward(WIDTH)
        self.assertEquals(self.term.reportCursorPosition(), (WIDTH, 0))

    def testCursorBackward(self):
        self.term.cursorForward(10)
        self.term.cursorBackward(2)
        self.assertEquals(self.term.reportCursorPosition(), (8, 0))
        self.term.cursorBackward(7)
        self.assertEquals(self.term.reportCursorPosition(), (1, 0))
        self.term.cursorBackward(1)
        self.assertEquals(self.term.reportCursorPosition(), (0, 0))
        self.term.cursorBackward(1)
        self.assertEquals(self.term.reportCursorPosition(), (0, 0))

    def testSimpleWriting(self):
        s = "Hello, world."
        self.term.write(s)
        self.assertEquals(
            str(self.term),
            s + (self.term.fill * (WIDTH - len(s))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in range(HEIGHT - 1)]))

    def testWritingInTheMiddle(self):
        s = "Hello, world."
        self.term.cursorDown(5)
        self.term.cursorForward(5)
        self.term.write(s)
        self.assertEquals(
            str(self.term),
            '\n'.join([self.term.fill * WIDTH for i in range(5)]) + '\n' +
            (self.term.fill * 5) + s + (self.term.fill * (WIDTH - 5 - len(s))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in range(HEIGHT - 6)]))

    def testWritingWrappedAtEndOfLine(self):
        s = "Hello, world."
        self.term.cursorForward(WIDTH - 5)
        self.term.write(s)
        self.assertEquals(
            str(self.term),
            (self.term.fill * (WIDTH - 5) + s[:5]) + '\n' +
            s[5:] + (self.term.fill * (WIDTH - len(s[5:]))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 2)]))

    def testIndex(self):
        self.term.index()
        self.assertEquals(self.term.reportCursorPosition(), (0, 1))
        self.term.cursorDown(HEIGHT)
        self.assertEquals(self.term.reportCursorPosition(), (0, HEIGHT - 1))
        self.term.index()
        self.assertEquals(self.term.reportCursorPosition(), (0, HEIGHT - 1))

    def testReverseIndex(self):
        self.term.reverseIndex()
        self.assertEquals(self.term.reportCursorPosition(), (0, 0))
        self.term.cursorDown(2)
        self.assertEquals(self.term.reportCursorPosition(), (0, 2))
        self.term.reverseIndex()
        self.assertEquals(self.term.reportCursorPosition(), (0, 1))

class Loopback(unittest.TestCase):
    def setUp(self):
        self.server = ServerProtocol()
        self.client = ClientProtocol(TerminalBuffer)
