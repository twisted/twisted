
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

from pyunit import unittest

import cStringIO
import sys
# Twisted Imports
from twisted.spread import banana
from twisted.protocols import protocol

class MathTestCase(unittest.TestCase):
    def testInt2b128(self):
        funkylist = range(0,100) + range(1000,1100) + range(1000000,1000100) + [1024 **10l]
        for i in funkylist:
            x = cStringIO.StringIO()
            banana.int2b128(i, x.write)
            v = x.getvalue()
            y = banana.b1282int(v)
            assert y == i, "y = %s; i = %s" % (y,i)

class BananaTestCase(unittest.TestCase):

    encClass = banana.Pynana
    
    def setUp(self):
        self.io = cStringIO.StringIO()
        self.enc = self.encClass()
        self.enc.makeConnection(protocol.FileWrapper(self.io))
        self.enc._selectDialect("none")
        self.enc.expressionReceived = self.putResult

    def putResult(self, result):
        self.result = result

    def tearDown(self):
        self.enc.connectionLost()
        del self.enc

    def testString(self):
        self.enc.sendEncoded("hello")
        l = []
        self.enc.dataReceived(self.io.getvalue())
        assert self.result == 'hello'

    def testLong(self):
        self.enc.sendEncoded(1015l)
        self.enc.dataReceived(self.io.getvalue())
        assert self.result == 1015l, "should be 1015l, got %s" % self.result
        
    def testNegativeLong(self):
        self.enc.sendEncoded(-1015l)
        self.enc.dataReceived(self.io.getvalue())
        assert self.result == -1015l, "should be -1015l, got %s" % self.result

    def testInteger(self):
        self.enc.sendEncoded(1015)
        self.enc.dataReceived(self.io.getvalue())
        assert self.result == 1015, "should be 1015, got %s" % self.result

    def testNegative(self):
        self.enc.sendEncoded(-1015)
        self.enc.dataReceived(self.io.getvalue())
        assert self.result == -1015, "should be -1015, got %s" % self.result
        
    def testFloat(self):
        self.enc.sendEncoded(1015.)
        self.enc.dataReceived(self.io.getvalue())
        assert self.result == 1015.

    def testList(self):
        foo = [1, 2, [3, 4], [30.5, 40.2], 5, ["six", "seven", ["eight", 9]], [10], []]
        self.enc.sendEncoded(foo)
        self.enc.dataReceived(self.io.getvalue())
        assert self.result == foo, "%s!=%s" % (repr(self.result), repr(self.result))

    def testPartial(self):
        foo = [1, 2, [3, 4], [30.5, 40.2], 5,
               ["six", "seven", ["eight", 9]], [10],
               # TODO: currently the C implementation's a bit buggy...
               sys.maxint * 3l, sys.maxint * 2l, sys.maxint * -2l]
        self.enc.sendEncoded(foo)
        for byte in self.io.getvalue():
            self.enc.dataReceived(byte)
        assert self.result == foo, "%s!=%s" % (repr(self.result), repr(foo))

testCases = [MathTestCase, BananaTestCase]

if hasattr(banana, 'cBanana'):
    class CananaTestCase(BananaTestCase):
    
        encClass = banana.Canana
    testCases.append(CananaTestCase)


