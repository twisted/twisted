# -*- test-case-name: twisted.conch.test.test_manhole -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.manhole}.
"""

import traceback

from twisted.trial import unittest
from twisted.internet import error, defer
from twisted.test.proto_helpers import StringTransport
from twisted.conch.test.test_recvline import _TelnetMixin, _SSHMixin, _StdioMixin, stdio, ssh
from twisted.conch import manhole
from twisted.conch.insults import insults


def determineDefaultFunctionName():
    """
    Return the string used by Python as the name for code objects which are
    compiled from interactive input or at the top-level of modules.
    """
    try:
        1 / 0
    except:
        # The last frame is this function.  The second to last frame is this
        # function's caller, which is module-scope, which is what we want,
        # so -2.
        return traceback.extract_stack()[-2][2]
defaultFunctionName = determineDefaultFunctionName()



class ManholeInterpreterTests(unittest.TestCase):
    """
    Tests for L{manhole.ManholeInterpreter}.
    """
    def test_resetBuffer(self):
        """
        L{ManholeInterpreter.resetBuffer} should empty the input buffer.
        """
        interpreter = manhole.ManholeInterpreter(None)
        interpreter.buffer.extend(["1", "2"])
        interpreter.resetBuffer()
        self.assertFalse(interpreter.buffer)



class ManholeProtocolTests(unittest.TestCase):
    """
    Tests for L{manhole.Manhole}.
    """
    def test_interruptResetsInterpreterBuffer(self):
        """
        L{manhole.Manhole.handle_INT} should cause the interpreter input buffer
        to be reset.
        """
        transport = StringTransport()
        terminal = insults.ServerProtocol(manhole.Manhole)
        terminal.makeConnection(transport)
        protocol = terminal.terminalProtocol
        interpreter = protocol.interpreter
        interpreter.buffer.extend(["1", "2"])
        protocol.handle_INT()
        self.assertFalse(interpreter.buffer)



class WriterTestCase(unittest.TestCase):
    def testInteger(self):
        manhole.lastColorizedLine("1")


    def testDoubleQuoteString(self):
        manhole.lastColorizedLine('"1"')


    def testSingleQuoteString(self):
        manhole.lastColorizedLine("'1'")


    def testTripleSingleQuotedString(self):
        manhole.lastColorizedLine("'''1'''")


    def testTripleDoubleQuotedString(self):
        manhole.lastColorizedLine('"""1"""')


    def testFunctionDefinition(self):
        manhole.lastColorizedLine("def foo():")


    def testClassDefinition(self):
        manhole.lastColorizedLine("class foo:")


class ManholeLoopbackMixin:
    serverProtocol = manhole.ColoredManhole

    def wfd(self, d):
        return defer.waitForDeferred(d)

    def testSimpleExpression(self):
        done = self.recvlineClient.expect("done")

        self._testwrite(
            "1 + 1\n"
            "done")

        def finished(ign):
            self._assertBuffer(
                [">>> 1 + 1",
                 "2",
                 ">>> done"])

        return done.addCallback(finished)

    def testTripleQuoteLineContinuation(self):
        done = self.recvlineClient.expect("done")

        self._testwrite(
            "'''\n'''\n"
            "done")

        def finished(ign):
            self._assertBuffer(
                [">>> '''",
                 "... '''",
                 "'\\n'",
                 ">>> done"])

        return done.addCallback(finished)

    def testFunctionDefinition(self):
        done = self.recvlineClient.expect("done")

        self._testwrite(
            "def foo(bar):\n"
            "\tprint bar\n\n"
            "foo(42)\n"
            "done")

        def finished(ign):
            self._assertBuffer(
                [">>> def foo(bar):",
                 "...     print bar",
                 "... ",
                 ">>> foo(42)",
                 "42",
                 ">>> done"])

        return done.addCallback(finished)

    def testClassDefinition(self):
        done = self.recvlineClient.expect("done")

        self._testwrite(
            "class Foo:\n"
            "\tdef bar(self):\n"
            "\t\tprint 'Hello, world!'\n\n"
            "Foo().bar()\n"
            "done")

        def finished(ign):
            self._assertBuffer(
                [">>> class Foo:",
                 "...     def bar(self):",
                 "...         print 'Hello, world!'",
                 "... ",
                 ">>> Foo().bar()",
                 "Hello, world!",
                 ">>> done"])

        return done.addCallback(finished)

    def testException(self):
        done = self.recvlineClient.expect("done")

        self._testwrite(
            "raise Exception('foo bar baz')\n"
            "done")

        def finished(ign):
            self._assertBuffer(
                [">>> raise Exception('foo bar baz')",
                 "Traceback (most recent call last):",
                 '  File "<console>", line 1, in ' + defaultFunctionName,
                 "Exception: foo bar baz",
                 ">>> done"])

        return done.addCallback(finished)

    def testControlC(self):
        done = self.recvlineClient.expect("done")

        self._testwrite(
            "cancelled line" + manhole.CTRL_C +
            "done")

        def finished(ign):
            self._assertBuffer(
                [">>> cancelled line",
                 "KeyboardInterrupt",
                 ">>> done"])

        return done.addCallback(finished)


    def test_interruptDuringContinuation(self):
        """
        Sending ^C to Manhole while in a state where more input is required to
        complete a statement should discard the entire ongoing statement and
        reset the input prompt to the non-continuation prompt.
        """
        continuing = self.recvlineClient.expect("things")

        self._testwrite("(\nthings")

        def gotContinuation(ignored):
            self._assertBuffer(
                [">>> (",
                 "... things"])
            interrupted = self.recvlineClient.expect(">>> ")
            self._testwrite(manhole.CTRL_C)
            return interrupted
        continuing.addCallback(gotContinuation)

        def gotInterruption(ignored):
            self._assertBuffer(
                [">>> (",
                 "... things",
                 "KeyboardInterrupt",
                 ">>> "])
        continuing.addCallback(gotInterruption)
        return continuing


    def testControlBackslash(self):
        self._testwrite("cancelled line")
        partialLine = self.recvlineClient.expect("cancelled line")

        def gotPartialLine(ign):
            self._assertBuffer(
                [">>> cancelled line"])
            self._testwrite(manhole.CTRL_BACKSLASH)

            d = self.recvlineClient.onDisconnection
            return self.assertFailure(d, error.ConnectionDone)

        def gotClearedLine(ign):
            self._assertBuffer(
                [""])

        return partialLine.addCallback(gotPartialLine).addCallback(gotClearedLine)

    def testControlD(self):
        self._testwrite("1 + 1")
        helloWorld = self.wfd(self.recvlineClient.expect(r"\+ 1"))
        yield helloWorld
        helloWorld.getResult()
        self._assertBuffer([">>> 1 + 1"])

        self._testwrite(manhole.CTRL_D + " + 1")
        cleared = self.wfd(self.recvlineClient.expect(r"\+ 1"))
        yield cleared
        cleared.getResult()
        self._assertBuffer([">>> 1 + 1 + 1"])

        self._testwrite("\n")
        printed = self.wfd(self.recvlineClient.expect("3\n>>> "))
        yield printed
        printed.getResult()

        self._testwrite(manhole.CTRL_D)
        d = self.recvlineClient.onDisconnection
        disconnected = self.wfd(self.assertFailure(d, error.ConnectionDone))
        yield disconnected
        disconnected.getResult()
    testControlD = defer.deferredGenerator(testControlD)


    def testControlL(self):
        """
        CTRL+L is generally used as a redraw-screen command in terminal
        applications.  Manhole doesn't currently respect this usage of it,
        but it should at least do something reasonable in response to this
        event (rather than, say, eating your face).
        """
        # Start off with a newline so that when we clear the display we can
        # tell by looking for the missing first empty prompt line.
        self._testwrite("\n1 + 1")
        helloWorld = self.wfd(self.recvlineClient.expect(r"\+ 1"))
        yield helloWorld
        helloWorld.getResult()
        self._assertBuffer([">>> ", ">>> 1 + 1"])

        self._testwrite(manhole.CTRL_L + " + 1")
        redrew = self.wfd(self.recvlineClient.expect(r"1 \+ 1 \+ 1"))
        yield redrew
        redrew.getResult()
        self._assertBuffer([">>> 1 + 1 + 1"])
    testControlL = defer.deferredGenerator(testControlL)


    def testDeferred(self):
        self._testwrite(
            "from twisted.internet import defer, reactor\n"
            "d = defer.Deferred()\n"
            "d\n")

        deferred = self.wfd(self.recvlineClient.expect("<Deferred #0>"))
        yield deferred
        deferred.getResult()

        self._testwrite(
            "c = reactor.callLater(0.1, d.callback, 'Hi!')\n")
        delayed = self.wfd(self.recvlineClient.expect(">>> "))
        yield delayed
        delayed.getResult()

        called = self.wfd(self.recvlineClient.expect("Deferred #0 called back: 'Hi!'\n>>> "))
        yield called
        called.getResult()
        self._assertBuffer(
            [">>> from twisted.internet import defer, reactor",
             ">>> d = defer.Deferred()",
             ">>> d",
             "<Deferred #0>",
             ">>> c = reactor.callLater(0.1, d.callback, 'Hi!')",
             "Deferred #0 called back: 'Hi!'",
             ">>> "])

    testDeferred = defer.deferredGenerator(testDeferred)

class ManholeLoopbackTelnet(_TelnetMixin, unittest.TestCase, ManholeLoopbackMixin):
    pass

class ManholeLoopbackSSH(_SSHMixin, unittest.TestCase, ManholeLoopbackMixin):
    if ssh is None:
        skip = "Crypto requirements missing, can't run manhole tests over ssh"

class ManholeLoopbackStdio(_StdioMixin, unittest.TestCase, ManholeLoopbackMixin):
    if stdio is None:
        skip = "Terminal requirements missing, can't run manhole tests over stdio"
    else:
        serverProtocol = stdio.ConsoleManhole
