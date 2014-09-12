# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test suite for asyncronous I/O support for Windows Console.

For testing I use the low level WriteConsoleInput function that allows
writing directly into the console input queue.
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
    stdin = win32conio.GetStdHandle("CONIN$")


class ConInTestCase(unittest.TestCase):
    """
    Test case for console stdin.
    """
    def setUp(self):
        self.console = win32conio.Console()
        self.console.setEcho(False)

    def tearDown(self):
        self.console.closeRead()
        self.console.closeWrite()

    def testRead(self):
        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "hello\r\n")

    def testRead2(self):
        """
        Test two consecutives read.
        """

        def read():
            data = u"hello\r"
            records = [createKeyEvent(c) for c in data]
            stdin.WriteConsoleInput(records)

            result = self.console.read()
            self.failUnlessEqual(result, "hello\r\n")

        read()
        read()

    def testReadMultiple(self):
        """
        Test if repeated characters are handled correctly.
        """

        data = u"hello\r"
        records = [createKeyEvent(c, 3) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "hhheeellllllooo\r\n")

    def testReadWithDelete(self):
        """
        Test if deletion is handled correctly.
        """

        data = u"hello" + u"\b" * 5 + u"world\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "world\r\n")

    def testDeleteBoundary(self):
        """
        Test if deletion is handled correctly.
        """

        data = u"h" + "\b\b" + u"w\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "w\r\n")

    def testDeleteFullBoundary(self):
        """
        Test if deletion is handled correctly.
        """

        data = u"h" * 500 + "\b" * 600 + u"w\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "w\r\n")

#   def testReadWithBuffer(self):
#       data = u"hello\r"
#       records = [createKeyEvent(c) for c in data]
#       stdin.WriteConsoleInput(records)

#       result = self.stdin.read(3)
#       self.failUnlessEqual(result, "hel")

#       result = self.stdin.read(3)
#       self.failUnlessEqual(result, "lo\r")

    def testReadWouldBlock(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        self.failUnlessEqual('', self.console.read())

#   def testReadWouldBlockBuffer(self):
#       data = u"hello"
#       records = [createKeyEvent(c) for c in data]
#       stdin.WriteConsoleInput(records)

#       self.failUnlessRaises(IOError, self.stdin.read, 3)

    def testIsatty(self):
        self.failUnless(self.console.isatty())

    def testBuffer(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        try:
            # This will put the data in the accumulation buffer
            self.console.read()
        except IOError:
            pass

        self.failUnlessEqual(self.console._inbuf, "hello")

    def testFlush(self):
        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        self.console.flushIn()

        self.failIf(self.console.inbuffer)
        self.failUnlessEqual('', self.console.read())

    def testFlushBuffer(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        try:
            # This will put the data in the accumulation buffer
            self.console.read()
        except IOError:
            pass

        self.console.flushIn()

        self.failIf(self.console.inbuffer)
        self.failIf(self.console._inbuf)
        self.failUnlessEqual('', self.console.read())


class ConInRawTestCase(unittest.TestCase):
    """
    Test case for console stdin in raw mode.
    """

    def setUp(self):
        self.console = win32conio.Console()
        self.console.setEcho(False)
        self.console.enableRawMode()

    def tearDown(self):
        self.console.closeRead()
        self.console.closeWrite()

    def testRead(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "hello")

    def testReadMultiple(self):
        data = u"hello"
        records = [createKeyEvent(c, 3) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "hhheeellllllooo")

    def testReadWithDelete(self):
        data = u"hello" + u'\b' * 5 + u"world"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        result = self.console.read()
        self.failUnlessEqual(result, "hello" + '\b' * 5 + "world")

#   def testReadWithBuffer(self):
#       data = u"hello\r"
#       records = [createKeyEvent(c) for c in data]
#       stdin.WriteConsoleInput(records)

#       result = self.console.read(3)
#       self.failUnlessEqual(result, "hel")

#       result = self.console.read(3)
#       self.failUnlessEqual(result, "lo\n")

    def testFlush(self):
        data = u"hello"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)

        self.console.flushIn()

        self.failIf(self.console.inbuffer)
        self.failIf(self.console.read())


class ConOutTestCase(unittest.TestCase):
    """
    Test case for console stdout.
    Not very much to test, yet.
    """

    def setUp(self):
        self.console = win32conio.Console()
        self.console.setEcho(False)
        self.console.enableRawMode()

    def tearDown(self):
        self.console.closeRead()
        self.console.closeWrite()

    def testWrite(self):
        data = "hello"
        n = self.console.write(data)

        self.failUnlessEqual(n, 5)

    def testWriteUnicode(self):
        data = u"hello"
        n = self.console.write(data)

        self.failUnlessEqual(n, 5)

    def testWritelines(self):
        data = ["hello", "world"]
        n = self.console.writelines(data)

        self.failUnlessEqual(n, 10)

    def testIsatty(self):
        self.failUnless(self.console.isatty())


class StdIOTestProtocol(protocol.Protocol):
    def makeConnection(self, transport):
        self.onData = defer.Deferred()

    def dataReceived(self, data):
        self.onData.callback(data)


class StdIOTestCase(unittest.TestCase):
    """
    Test twisted.internet.stdio support for consoles.
    """

    def setUp(self):
        p = StdIOTestProtocol()
        self.stdio = stdio.StandardIO(p, True)
        self.stdio.setEcho(False)
        self.onData = p.onData

    def tearDown(self):
        self.stdio._pause()
        try:
            self.stdio._stopPolling()
        except error.AlreadyCalled:
            pass

    def testRead(self):
        def cb(result):
            self.failUnlessEqual(result, "hello\r\n")
            self.stdio.loseConnection()

        d = self.onData.addCallback(cb)
        data = u"hello\r"
        records = [createKeyEvent(c) for c in data]
        stdin.WriteConsoleInput(records)
        return d
        
if win32console is None:
    ConInTestCase.skip = "win32conio is only available under Windows."
    ConInRawTestCase.skip = "win32conio is only available under Windows."
    ConOutTestCase.skip = "win32conio is only available under Windows."
    StdIOTestCase.skip = "win32conio is only available under Windows."
