
from helper import TerminalBuffer
from insults import ServerProtocol, ClientProtocol
from insults import G0, G1, G2, G3
from insults import IRM
from insults import NORMAL, BOLD, UNDERLINE, BLINK, REVERSE_VIDEO

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

    def testCursorPositioning(self):
        self.term.cursorPosition(3, 9)
        self.assertEquals(self.term.reportCursorPosition(), (3, 9))

    def testSimpleWriting(self):
        s = "Hello, world."
        self.term.write(s)
        self.assertEquals(
            str(self.term),
            s + (self.term.fill * (WIDTH - len(s))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 1)]))

    def testOvertype(self):
        s = "hello, world."
        self.term.write(s)
        self.term.cursorBackward(len(s))
        self.term.setModes([IRM])
        self.term.write("H")
        self.assertEquals(
            str(self.term),
            ("H" + s[1:]) + (self.term.fill * (WIDTH - len(s))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 1)]))

    def testInsert(self):
        s = "ello, world."
        self.term.write(s)
        self.term.cursorBackward(len(s))
        self.term.write("H")
        self.assertEquals(
            str(self.term),
            ("H" + s) + (self.term.fill * (WIDTH - len(s) - 1)) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 1)]))

    def testWritingInTheMiddle(self):
        s = "Hello, world."
        self.term.cursorDown(5)
        self.term.cursorForward(5)
        self.term.write(s)
        self.assertEquals(
            str(self.term),
            '\n'.join([self.term.fill * WIDTH for i in xrange(5)]) + '\n' +
            (self.term.fill * 5) + s + (self.term.fill * (WIDTH - 5 - len(s))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 6)]))

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

    def testNextLine(self):
        self.term.nextLine()
        self.assertEquals(self.term.reportCursorPosition(), (0, 1))
        self.term.cursorForward(5)
        self.assertEquals(self.term.reportCursorPosition(), (5, 1))
        self.term.nextLine()
        self.assertEquals(self.term.reportCursorPosition(), (0, 2))

    def testSaveCursor(self):
        self.term.cursorDown(5)
        self.term.cursorForward(7)
        self.assertEquals(self.term.reportCursorPosition(), (7, 5))
        self.term.saveCursor()
        self.term.cursorDown(7)
        self.term.cursorBackward(3)
        self.assertEquals(self.term.reportCursorPosition(), (4, 12))
        self.term.restoreCursor()
        self.assertEquals(self.term.reportCursorPosition(), (7, 5))

    def testSingleShifts(self):
        self.term.singleShift2()
        self.term.write('Hi')

        ch = self.term.getCharacter(0, 0)
        self.assertEquals(ch[0], 'H')
        self.assertEquals(ch[1].charset, G2)

        ch = self.term.getCharacter(1, 0)
        self.assertEquals(ch[0], 'i')
        self.assertEquals(ch[1].charset, G0)

        self.term.singleShift3()
        self.term.write('!!')

        ch = self.term.getCharacter(2, 0)
        self.assertEquals(ch[0], '!')
        self.assertEquals(ch[1].charset, G3)

        ch = self.term.getCharacter(3, 0)
        self.assertEquals(ch[0], '!')
        self.assertEquals(ch[1].charset, G0)

    def testShifting(self):
        s1 = "Hello"
        s2 = "World"
        s3 = "Bye!"
        self.term.write("Hello\n")
        self.term.shiftOut()
        self.term.write("World\n")
        self.term.shiftIn()
        self.term.write("Bye!\n")

        g = G0
        h = 0
        for s in (s1, s2, s3):
            for i in range(len(s)):
                ch = self.term.getCharacter(i, h)
                self.assertEquals(ch[0], s[i])
                self.assertEquals(ch[1].charset, g)
            g = g == G0 and G1 or G0
            h += 1

    def testGraphicRendition(self):
        self.term.selectGraphicRendition(BOLD, UNDERLINE, BLINK, REVERSE_VIDEO)
        self.term.write('W')
        self.term.selectGraphicRendition(NORMAL)
        self.term.write('X')
        self.term.selectGraphicRendition(BLINK)
        self.term.write('Y')
        self.term.selectGraphicRendition(BOLD)
        self.term.write('Z')

        ch = self.term.getCharacter(0, 0)
        self.assertEquals(ch[0], 'W')
        self.failUnless(ch[1].bold)
        self.failUnless(ch[1].underline)
        self.failUnless(ch[1].blink)
        self.failUnless(ch[1].reverseVideo)

        ch = self.term.getCharacter(1, 0)
        self.assertEquals(ch[0], 'X')
        self.failIf(ch[1].bold)
        self.failIf(ch[1].underline)
        self.failIf(ch[1].blink)
        self.failIf(ch[1].reverseVideo)

        ch = self.term.getCharacter(2, 0)
        self.assertEquals(ch[0], 'Y')
        self.failUnless(ch[1].blink)
        self.failIf(ch[1].bold)
        self.failIf(ch[1].underline)
        self.failIf(ch[1].reverseVideo)

        ch = self.term.getCharacter(3, 0)
        self.assertEquals(ch[0], 'Z')
        self.failUnless(ch[1].blink)
        self.failUnless(ch[1].bold)
        self.failIf(ch[1].underline)
        self.failIf(ch[1].reverseVideo)

    def testEraseLine(self):
        s1 = 'line 1'
        s2 = 'line 2'
        s3 = 'line 3'
        self.term.write('\n'.join((s1, s2, s3)) + '\n')
        self.term.cursorPosition(1, 1)
        self.term.eraseLine()

        self.assertEquals(
            str(self.term),
            s1 + (self.term.fill * (WIDTH - len(s1))) + '\n' +
            (self.term.fill * WIDTH) + '\n' +
            s3 + (self.term.fill * (WIDTH - len(s3))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 3)]))

    def testEraseToLineEnd(self):
        s = 'Hello, world.'
        self.term.write(s)
        self.term.cursorBackward(5)
        self.term.eraseToLineEnd()
        self.assertEquals(
            str(self.term),
            s[:-5] + (self.term.fill * (WIDTH - (len(s) - 5))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 1)]))

    def testEraseToLineBeginning(self):
        s = 'Hello, world.'
        self.term.write(s)
        self.term.cursorBackward(5)
        self.term.eraseToLineBeginning()
        self.assertEquals(
            str(self.term),
            (self.term.fill * (len(s) - 4)) + s[-4:] + (self.term.fill * (WIDTH - len(s))) + '\n' +
            '\n'.join([self.term.fill * WIDTH for i in xrange(HEIGHT - 1)]))
