"""
testcases for twisted.sexpy
"""

from twisted import sexpy
from pyunit import unittest

class DummySExp(sexpy.SymbolicExpressionReceiver):
    current = None
    def symbolicExpressionReceived(self, expr):
        self.current = expr

class SymbolicExpressionReceiverTestCase(unittest.TestCase):
    """
    A test case for the receiver
    """
    sexpTestData = [
        ("test ", sexpy.atom("test")),
        ('"test"', 'test'),
        ("(10 -20  30 )", [10, -20, 30]),
        ("(ten 20 \"thirty\" (forty fifty))", [sexpy.atom("ten"), 20, 'thirty', [sexpy.atom("forty"), sexpy.atom("fifty")]])
        ]
    
    def setUp(self):
        self.sexpr = DummySExp()
        self.sexpr.connectionMade()

    def testSymbolicExpressionReceived(self):
        for data, value in self.sexpTestData:
            for byte in data:
                self.sexpr.dataReceived(byte)
            current = self.sexpr.current
            assert current == value,\
                   "mismatch. wrote: %s expected: %s received: %s" %\
                   (repr(data), repr(value), repr(current))


testCases = [SymbolicExpressionReceiverTestCase]
