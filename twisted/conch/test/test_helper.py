# -*- test-case-name: twisted.conch.test.test_helper -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.conch.insults import helper
from twisted.conch.insults.insults import G0, G1, G2, G3
from twisted.conch.insults.insults import modes, privateModes
from twisted.conch.insults.insults import NORMAL, BOLD, UNDERLINE, BLINK, REVERSE_VIDEO

from twisted.trial import unittest

WIDTH = 80
HEIGHT = 24

class BufferTestCase(unittest.TestCase):
    def setUp(self):
        self.term = helper.TerminalBuffer()
        self.term.connectionMade()

    def testInitialState(self):
        self.assertEquals(self.term.width, WIDTH)
        self.assertEquals(self.term.height, HEIGHT)
        self.assertEquals(str(self.term),
                          '\n' * (HEIGHT - 1))
        self.assertEquals(self.term.reportCursorPosition(), (0, 0))


    def test_initialPrivateModes(self):
        """
        Verify that only DEC Auto Wrap Mode (DECAWM) and DEC Text Cursor Enable
        Mode (DECTCEM) are initially in the Set Mode (SM) state.
        """
        self.assertEqual(
            {privateModes.AUTO_WRAP: True,
             privateModes.CURSOR_MODE: True},
            self.term.privateModes)


    def test_carriageReturn(self):
        """
        C{"\r"} moves the cursor to the first column in the current row.
        """
        self.term.cursorForward(5)
        self.term.cursorDown(3)
        self.assertEqual(self.term.reportCursorPosition(), (5, 3))
        self.term.insertAtCursor("\r")
        self.assertEqual(self.term.reportCursorPosition(), (0, 3))


    def test_linefeed(self):
        """
        C{"\n"} moves the cursor to the next row without changing the column.
        """
        self.term.cursorForward(5)
        self.assertEqual(self.term.reportCursorPosition(), (5, 0))
        self.term.insertAtCursor("\n")
        self.assertEqual(self.term.reportCursorPosition(), (5, 1))


    def test_newline(self):
        """
        C{write} transforms C{"\n"} into C{"\r\n"}.
        """
        self.term.cursorForward(5)
        self.term.cursorDown(3)
        self.assertEqual(self.term.reportCursorPosition(), (5, 3))
        self.term.write("\n")
        self.assertEqual(self.term.reportCursorPosition(), (0, 4))


    def test_setPrivateModes(self):
        """
        Verify that L{helper.TerminalBuffer.setPrivateModes} changes the Set
        Mode (SM) state to "set" for the private modes it is passed.
        """
        expected = self.term.privateModes.copy()
        self.term.setPrivateModes([privateModes.SCROLL, privateModes.SCREEN])
        expected[privateModes.SCROLL] = True
        expected[privateModes.SCREEN] = True
        self.assertEqual(expected, self.term.privateModes)


    def test_resetPrivateModes(self):
        """
        Verify that L{helper.TerminalBuffer.resetPrivateModes} changes the Set
        Mode (SM) state to "reset" for the private modes it is passed.
        """
        expected = self.term.privateModes.copy()
        self.term.resetPrivateModes([privateModes.AUTO_WRAP, privateModes.CURSOR_MODE])
        del expected[privateModes.AUTO_WRAP]
        del expected[privateModes.CURSOR_MODE]
        self.assertEqual(expected, self.term.privateModes)


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
            s + '\n' +
            '\n' * (HEIGHT - 2))

    def testOvertype(self):
        s = "hello, world."
        self.term.write(s)
        self.term.cursorBackward(len(s))
        self.term.resetModes([modes.IRM])
        self.term.write("H")
        self.assertEquals(
            str(self.term),
            ("H" + s[1:]) + '\n' +
            '\n' * (HEIGHT - 2))

    def testInsert(self):
        s = "ello, world."
        self.term.write(s)
        self.term.cursorBackward(len(s))
        self.term.setModes([modes.IRM])
        self.term.write("H")
        self.assertEquals(
            str(self.term),
            ("H" + s) + '\n' +
            '\n' * (HEIGHT - 2))

    def testWritingInTheMiddle(self):
        s = "Hello, world."
        self.term.cursorDown(5)
        self.term.cursorForward(5)
        self.term.write(s)
        self.assertEquals(
            str(self.term),
            '\n' * 5 +
            (self.term.fill * 5) + s + '\n' +
            '\n' * (HEIGHT - 7))

    def testWritingWrappedAtEndOfLine(self):
        s = "Hello, world."
        self.term.cursorForward(WIDTH - 5)
        self.term.write(s)
        self.assertEquals(
            str(self.term),
            s[:5].rjust(WIDTH) + '\n' +
            s[5:] + '\n' +
            '\n' * (HEIGHT - 3))

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

    def test_nextLine(self):
        """
        C{nextLine} positions the cursor at the beginning of the row below the
        current row.
        """
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

    def testColorAttributes(self):
        s1 = "Merry xmas"
        s2 = "Just kidding"
        self.term.selectGraphicRendition(helper.FOREGROUND + helper.RED,
                                         helper.BACKGROUND + helper.GREEN)
        self.term.write(s1 + "\n")
        self.term.selectGraphicRendition(NORMAL)
        self.term.write(s2 + "\n")

        for i in range(len(s1)):
            ch = self.term.getCharacter(i, 0)
            self.assertEquals(ch[0], s1[i])
            self.assertEquals(ch[1].charset, G0)
            self.assertEquals(ch[1].bold, False)
            self.assertEquals(ch[1].underline, False)
            self.assertEquals(ch[1].blink, False)
            self.assertEquals(ch[1].reverseVideo, False)
            self.assertEquals(ch[1].foreground, helper.RED)
            self.assertEquals(ch[1].background, helper.GREEN)

        for i in range(len(s2)):
            ch = self.term.getCharacter(i, 1)
            self.assertEquals(ch[0], s2[i])
            self.assertEquals(ch[1].charset, G0)
            self.assertEquals(ch[1].bold, False)
            self.assertEquals(ch[1].underline, False)
            self.assertEquals(ch[1].blink, False)
            self.assertEquals(ch[1].reverseVideo, False)
            self.assertEquals(ch[1].foreground, helper.WHITE)
            self.assertEquals(ch[1].background, helper.BLACK)

    def testEraseLine(self):
        s1 = 'line 1'
        s2 = 'line 2'
        s3 = 'line 3'
        self.term.write('\n'.join((s1, s2, s3)) + '\n')
        self.term.cursorPosition(1, 1)
        self.term.eraseLine()

        self.assertEquals(
            str(self.term),
            s1 + '\n' +
            '\n' +
            s3 + '\n' +
            '\n' * (HEIGHT - 4))

    def testEraseToLineEnd(self):
        s = 'Hello, world.'
        self.term.write(s)
        self.term.cursorBackward(5)
        self.term.eraseToLineEnd()
        self.assertEquals(
            str(self.term),
            s[:-5] + '\n' +
            '\n' * (HEIGHT - 2))

    def testEraseToLineBeginning(self):
        s = 'Hello, world.'
        self.term.write(s)
        self.term.cursorBackward(5)
        self.term.eraseToLineBeginning()
        self.assertEquals(
            str(self.term),
            s[-4:].rjust(len(s)) + '\n' +
            '\n' * (HEIGHT - 2))

    def testEraseDisplay(self):
        self.term.write('Hello world\n')
        self.term.write('Goodbye world\n')
        self.term.eraseDisplay()

        self.assertEquals(
            str(self.term),
            '\n' * (HEIGHT - 1))

    def testEraseToDisplayEnd(self):
        s1 = "Hello world"
        s2 = "Goodbye world"
        self.term.write('\n'.join((s1, s2, '')))
        self.term.cursorPosition(5, 1)
        self.term.eraseToDisplayEnd()

        self.assertEquals(
            str(self.term),
            s1 + '\n' +
            s2[:5] + '\n' +
            '\n' * (HEIGHT - 3))

    def testEraseToDisplayBeginning(self):
        s1 = "Hello world"
        s2 = "Goodbye world"
        self.term.write('\n'.join((s1, s2)))
        self.term.cursorPosition(5, 1)
        self.term.eraseToDisplayBeginning()

        self.assertEquals(
            str(self.term),
            '\n' +
            s2[6:].rjust(len(s2)) + '\n' +
            '\n' * (HEIGHT - 3))

    def testLineInsertion(self):
        s1 = "Hello world"
        s2 = "Goodbye world"
        self.term.write('\n'.join((s1, s2)))
        self.term.cursorPosition(7, 1)
        self.term.insertLine()

        self.assertEquals(
            str(self.term),
            s1 + '\n' +
            '\n' +
            s2 + '\n' +
            '\n' * (HEIGHT - 4))

    def testLineDeletion(self):
        s1 = "Hello world"
        s2 = "Middle words"
        s3 = "Goodbye world"
        self.term.write('\n'.join((s1, s2, s3)))
        self.term.cursorPosition(9, 1)
        self.term.deleteLine()

        self.assertEquals(
            str(self.term),
            s1 + '\n' +
            s3 + '\n' +
            '\n' * (HEIGHT - 3))

class FakeDelayedCall:
    called = False
    cancelled = False
    def __init__(self, fs, timeout, f, a, kw):
        self.fs = fs
        self.timeout = timeout
        self.f = f
        self.a = a
        self.kw = kw

    def active(self):
        return not (self.cancelled or self.called)

    def cancel(self):
        self.cancelled = True
#        self.fs.calls.remove(self)

    def call(self):
        self.called = True
        self.f(*self.a, **self.kw)

class FakeScheduler:
    def __init__(self):
        self.calls = []

    def callLater(self, timeout, f, *a, **kw):
        self.calls.append(FakeDelayedCall(self, timeout, f, a, kw))
        return self.calls[-1]

class ExpectTestCase(unittest.TestCase):
    def setUp(self):
        self.term = helper.ExpectableBuffer()
        self.term.connectionMade()
        self.fs = FakeScheduler()

    def testSimpleString(self):
        result = []
        d = self.term.expect("hello world", timeout=1, scheduler=self.fs)
        d.addCallback(result.append)

        self.term.write("greeting puny earthlings\n")
        self.failIf(result)
        self.term.write("hello world\n")
        self.failUnless(result)
        self.assertEquals(result[0].group(), "hello world")
        self.assertEquals(len(self.fs.calls), 1)
        self.failIf(self.fs.calls[0].active())

    def testBrokenUpString(self):
        result = []
        d = self.term.expect("hello world")
        d.addCallback(result.append)

        self.failIf(result)
        self.term.write("hello ")
        self.failIf(result)
        self.term.write("worl")
        self.failIf(result)
        self.term.write("d")
        self.failUnless(result)
        self.assertEquals(result[0].group(), "hello world")


    def testMultiple(self):
        result = []
        d1 = self.term.expect("hello ")
        d1.addCallback(result.append)
        d2 = self.term.expect("world")
        d2.addCallback(result.append)

        self.failIf(result)
        self.term.write("hello")
        self.failIf(result)
        self.term.write(" ")
        self.assertEquals(len(result), 1)
        self.term.write("world")
        self.assertEquals(len(result), 2)
        self.assertEquals(result[0].group(), "hello ")
        self.assertEquals(result[1].group(), "world")

    def testSynchronous(self):
        self.term.write("hello world")

        result = []
        d = self.term.expect("hello world")
        d.addCallback(result.append)
        self.failUnless(result)
        self.assertEquals(result[0].group(), "hello world")

    def testMultipleSynchronous(self):
        self.term.write("goodbye world")

        result = []
        d1 = self.term.expect("bye")
        d1.addCallback(result.append)
        d2 = self.term.expect("world")
        d2.addCallback(result.append)

        self.assertEquals(len(result), 2)
        self.assertEquals(result[0].group(), "bye")
        self.assertEquals(result[1].group(), "world")

    def _cbTestTimeoutFailure(self, res):
        self.assert_(hasattr(res, 'type'))
        self.assertEqual(res.type, helper.ExpectationTimeout)

    def testTimeoutFailure(self):
        d = self.term.expect("hello world", timeout=1, scheduler=self.fs)
        d.addBoth(self._cbTestTimeoutFailure)
        self.fs.calls[0].call()

    def testOverlappingTimeout(self):
        self.term.write("not zoomtastic")

        result = []
        d1 = self.term.expect("hello world", timeout=1, scheduler=self.fs)
        d1.addBoth(self._cbTestTimeoutFailure)
        d2 = self.term.expect("zoom")
        d2.addCallback(result.append)

        self.fs.calls[0].call()

        self.assertEquals(len(result), 1)
        self.assertEquals(result[0].group(), "zoom")
