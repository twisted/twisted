
from twisted.trial import unittest

from test_recvline import _x

import manhole

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
