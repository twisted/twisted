
from twisted.trial import unittest

from test_recvline import _x

import manhole

ctrlc = '\x03'
ctrlq = '\x04'
ctrld = '\x1c'

class ManholeLoopback(_x, unittest.TestCase):
    serverProtocol = manhole.ColoredManhole

    def testSimpleExpression(self):
        self._test(
            "1 + 1\n",
            [">>> 1 + 1",
             "2",
             ">>>"])

    def testTripleQuoteLineContinuation(self):
        self._test(
            "'''\n'''\n",
            [">>> '''",
             "... '''",
             "'\\n'",
             ">>>"])

    def testFunctionDefinition(self):
        self._test(
            "def foo(bar):\n"
            "\tprint bar\n\n"
            "foo(42)\n",
            [">>> def foo(bar):",
             "...     print bar",
             "...",
             ">>> foo(42)",
             "42",
             ">>>"])

    def testClassDefinition(self):
        self._test(
            "class Foo:\n"
            "\tdef bar(self):\n"
            "\t\tprint 'Hello, world!'\n\n"
            "Foo().bar()\n",
            [">>> class Foo:",
             "...     def bar(self):",
             "...         print 'Hello, world!'",
             "...",
             ">>> Foo().bar()",
             "Hello, world!",
             ">>>"])

    def testException(self):
        self._test(
            "1 / 0\n",
            [">>> 1 / 0",
             "Traceback (most recent call last):",
             '  File "<console>", line 1, in ?',
             "ZeroDivisionError: integer division or modulo by zero",
             ">>>"])

    def testControlC(self):
        self._test(
            "cancelled line" + ctrlc,
            [">>> cancelled line",
             "KeyboardInterrupt",
             ">>>"])

    def testControlQ(self):
        self._test(
            "cancelled line" + ctrlq,
            [""])

    def testControlD(self):
        self._test(
            "cancelled line" + ctrld,
            [""])
