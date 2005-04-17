# -*- test-case-name: twisted.conch.test.test_manhole -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import time

from twisted.trial import unittest
from twisted.conch.test.test_recvline import _TelnetMixin, _SSHMixin, _StdioMixin, stdio, ssh
from twisted.conch import manhole

ctrlc = '\x03'
ctrlq = '\x04'
ctrld = '\x1c'

class ManholeLoopbackMixin:
    serverProtocol = manhole.ColoredManhole

    def testSimpleExpression(self):
        self._test(
            "1 + 1\n",
            [">>> 1 + 1",
             "2",
             ">>> "])

    def testTripleQuoteLineContinuation(self):
        self._test(
            "'''\n'''\n",
            [">>> '''",
             "... '''",
             "'\\n'",
             ">>> "])

    def testFunctionDefinition(self):
        self._test(
            "def foo(bar):\n"
            "\tprint bar\n\n"
            "foo(42)\n",
            [">>> def foo(bar):",
             "...     print bar",
             "... ",
             ">>> foo(42)",
             "42",
             ">>> "])

    def testClassDefinition(self):
        self._test(
            "class Foo:\n"
            "\tdef bar(self):\n"
            "\t\tprint 'Hello, world!'\n\n"
            "Foo().bar()\n",
            [">>> class Foo:",
             "...     def bar(self):",
             "...         print 'Hello, world!'",
             "... ",
             ">>> Foo().bar()",
             "Hello, world!",
             ">>> "])

    def testException(self):
        self._test(
            "1 / 0\n",
            [">>> 1 / 0",
             "Traceback (most recent call last):",
             '  File "<console>", line 1, in ?',
             "ZeroDivisionError: integer division or modulo by zero",
             ">>> "])

    def testControlC(self):
        self._test(
            "cancelled line" + ctrlc,
            [">>> cancelled line",
             "KeyboardInterrupt",
             ">>> "])

    def testControlQ(self):
        self._test(
            "cancelled line" + ctrlq,
            [""])

    def testControlD(self):
        self._test(
            "cancelled line" + ctrld,
            [""])

    # XXX This test has a race condition.
    def testDeferred(self):
        self._test(
            "from twisted.internet import defer, reactor\n"
            "def deferLater(n):\n"
            "\td = defer.Deferred()\n"
            "\treactor.callLater(n, d.callback, 'Hi!')\n"
            "\treturn d\n"
            "\n"
            "deferLater(3.0)\n"
            "print 'incomplete line",
            [">>> from twisted.internet import defer, reactor",
             ">>> def deferLater(n):",
             "...     d = defer.Deferred()",
             "...     reactor.callLater(n, d.callback, 'Hi!')",
             "...     return d",
             "... ",
             ">>> deferLater(3.0)",
             "<Deferred #0>",
             ">>> print 'incomplete line"])

        time.sleep(5)
        from twisted.internet import reactor
        reactor.iterate()

        self._test(
            "",
            [">>> from twisted.internet import defer, reactor",
             ">>> def deferLater(n):",
             "...     d = defer.Deferred()",
             "...     reactor.callLater(n, d.callback, 'Hi!')",
             "...     return d",
             "... ",
             ">>> deferLater(3.0)",
             "<Deferred #0>",
             "Deferred #0 called back: 'Hi!'",
             ">>> print 'incomplete line"])

class ManholeLoopbackTelnet(_TelnetMixin, unittest.TestCase, ManholeLoopbackMixin):
    pass

class ManholeLoopbackSSH(_SSHMixin, unittest.TestCase, ManholeLoopbackMixin):
    if ssh is None:
        skip = "Crypto requirements missing, can't run manhole tests over ssh"

class ManholeLoopbackStdio(_StdioMixin, unittest.TestCase, ManholeLoopbackMixin):
    if stdio is None:
        skip = "Terminal requirements missing, can't run manhole tests over stdio"
