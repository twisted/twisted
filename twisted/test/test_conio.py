# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test suite for asyncronous I/O support for Windows Console.

For testing I use the low level WriteConsoleInput function that allows
to write directly in the console input queue.
"""

from twisted.python.runtime import platform

import os, sys

if platform.isWindows():
    import win32console
    from twisted.internet import win32conio, _win32stdio as stdio
else:
    win32console = None

from twisted.trial import unittest
from twisted.python import filepath
from twisted.internet import error, defer, protocol, reactor





def createKeyEvent(char, repeat=1):
    """
    Create a low level record structure with the given character.
    """

    evt = win32console.PyINPUT_RECORDType(win32console.KEY_EVENT)
    evt.KeyDown = True
    evt.Char = char
    evt.RepeatCount = repeat

    return evt

if platform.isWindows():
    stdin = win32console.GetStdHandle(win32console.STD_INPUT_HANDLE)


class ConInTestCase(unittest.TestCase):
    """
    Test case for console stdin.
    """

    def tearDown(self):
        win32conio.stdin.flush()

    def testRead(self):
        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "hello\n")

    def testRead2(self):
        """
        Test two consecutives read.
        """

        def read():
            data = u"hello\r"
            records = [createKeyEvent(c) for c in data]
            stdin.WriteConsoleInput(records)

            result = win32conio.stdin.read()
            self.failUnlessEqual(result, "hello\n")

        read()
        read()

    def testReadMultiple(self):
        """
        Test if repeated characters are handled correctly.
        """

        data = u"hello\r"
        records = [createKeyEvent(c, 3) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "hhheeellllllooo\n\n\n")

    def testReadWithDelete(self):
        """
        Test if deletion is handled correctly.
        """

        data = u"hello" + u"\b" * 5 + u"world\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "world\n")

    def testDeleteBoundary(self):
        """
        Test if deletion is handled correctly.
        """

        data = u"h" + "\b\b" + u"w\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "w\n")

    def testDeleteFullBoundary(self):
        """
        Test if deletion is handled correctly.
        """

        data = u"h" * 500 + "\b" * 600 + u"w\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "w\n")

    def testReadWithBuffer(self):
        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read(3)
        self.failUnlessEqual(result, "hel")

        result = win32conio.stdin.read(3)
        self.failUnlessEqual(result, "lo\n")

    def testReadWouldBlock(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        self.failUnlessRaises(IOError, win32conio.stdin.read)

    def testReadWouldBlockBuffer(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        self.failUnlessRaises(IOError, win32conio.stdin.read, 3)

    def testIsatty(self):
        self.failUnless(win32conio.stdin.isatty())

    def testBuffer(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        try:
            # This will put the data in the accumulation buffer
            win32conio.stdin.read()
        except IOError:
            pass

        self.failUnlessEqual(win32conio.stdin._buf, list("hello"))

    def testFlush(self):
        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read(3)
        win32conio.stdin.flush()

        self.failIf(win32conio.stdin.buffer)
        self.failUnlessRaises(IOError, win32conio.stdin.read, 3)

    def testFlushBuffer(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        try:
            # This will put the data in the accumulation buffer
            win32conio.stdin.read()
        except IOError:
            pass

        win32conio.stdin.flush()

        self.failIf(win32conio.stdin.buffer)
        self.failIf(win32conio.stdin._buf)
        self.failUnlessRaises(IOError, win32conio.stdin.read, 3)


class ConInRawTestCase(unittest.TestCase):
    """
    Test case for console stdin in raw mode.
    """

    def setUp(self):
        win32conio.stdin.enableRawMode()

    def tearDown(self):
        win32conio.stdin.flush()
        win32conio.stdin.enableRawMode(False)

    def testRead(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "hello")

    def testReadMultiple(self):
        data = u"hello"
        records = [createKeyEvent(c, 3) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "hhheeellllllooo")

    def testReadWithDelete(self):
        data = u"hello" + u'\b' * 5 + u"world"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read()
        self.failUnlessEqual(result, "hello" + '\b' * 5 + "world")

    def testReadWithBuffer(self):
        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read(3)
        self.failUnlessEqual(result, "hel")

        result = win32conio.stdin.read(3)
        self.failUnlessEqual(result, "lo\n")

    def testFlush(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = win32conio.stdin.read(3)
        win32conio.stdin.flush()

        self.failIf(win32conio.stdin.buffer)
        self.failIf(win32conio.stdin.read())


class ConOutTestCase(unittest.TestCase):
    """
    Test case for console stdout.
    Not very much to test, yet.
    """

    def testWrite(self):
        data = "hello"
        n = win32conio.stdout.write(data)

        self.failUnlessEqual(n, 5)

    def testWriteUnicode(self):
        data = u"hello"
        n = win32conio.stdout.write(data)

        self.failUnlessEqual(n, 5)

    def testWritelines(self):
        data = ["hello", "world"]
        n = win32conio.stdout.writelines(data)

        self.failUnlessEqual(n, 10)

    def testIsatty(self):
        self.failUnless(win32conio.stdout.isatty())


class StdIOTestProtocol(protocol.Protocol):
    def __init__(self):
        self.onData = defer.Deferred()

    def dataReceived(self, data):
        self.onData.callback(data)


class StdIOTestCase(unittest.TestCase):
    """
    Test twisted.internet.stdio support for consoles.
    """

    def setUp(self):
        p = StdIOTestProtocol()
        self.stdio = stdio.StandardIO(p)
        self.onData = p.onData

    def tearDown(self):
        self.stdio._pause()
        try:
            self.stdio._stopPolling()
        except error.AlreadyCalled:
            pass

        win32conio.stdin.flush()

    def testRead(self):
        def cb(result):
            self.failUnlessEqual(result, "hello\n")

        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        return self.onData.addCallback(cb)
        
if win32console is None:
    ConInTestCase.skip = "win32conio is only available under Windows."
    ConInRawTestCase.skip = "win32conio is only available under Windows."
    ConOutTestCase.skip = "win32conio is only available under Windows."
    StdIOTestCase.skip = "win32conio is only available under Windows."
