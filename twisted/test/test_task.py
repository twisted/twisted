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

from twisted.trial import unittest

from twisted.internet import task
from twisted.internet import reactor

class TestException(Exception):
    pass

class LoopTestCase(unittest.TestCase):
    def testBasicFunction(self):
        L = []
        def foo(a, b, c=None, d=None):
            L.append((a, b, c, d))
        
        lc = task.LoopingCall(foo, "a", "b", d="d")
        d = lc.start(0.1)
        reactor.callLater(1, lc.stop)
        result = unittest.deferredResult(d)
        self.assertIdentical(lc, result)
        
        self.failUnless(9 <= len(L) <= 11)
        
        for (a, b, c, d) in L:
            self.assertEquals(a, "a")
            self.assertEquals(b, "b")
            self.assertEquals(c, None)
            self.assertEquals(d, "d")
    
    def testFailure(self):
        def foo(x):
            raise TestException(x)
        
        lc = task.LoopingCall(foo, "bar")
        d = lc.start(0.1)
        err = unittest.deferredError(d)
        err.trap(TestException)
