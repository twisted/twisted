
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
