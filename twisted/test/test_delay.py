
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
Test cases for delay module.
"""

from pyunit import unittest
from twisted.python import delay

class Looper:
    state = 0
    def __call__(self):
        self.state = self.state + 1
        if self.state == 5:
            delay.StopLooping()

class DelayedTestCase(unittest.TestCase):
    def setUp(self):
        self.delayed = delay.Delayed()
        self.flag = 0

    def tearDown(self):
        del self.delayed

    def setFlag(self, fl):
        self.flag = fl
        
    def testLater(self):
        assert self.flag == 0
        self.delayed.later(self.setFlag, ticks=0, args=(1,))
        assert self.flag == 0
        self.delayed.run()
        assert self.flag == 1

    def testStep(self):
        assert self.flag == 0
        self.delayed.step(self.setFlag, ticks=0, list=(1,2,3,4,5))
        assert self.flag == 0
        self.delayed.run()
        assert self.flag == 1
        self.delayed.run()
        assert self.flag == 2
        self.delayed.run()
        assert self.flag == 3
        self.delayed.run()
        assert self.flag == 4
        self.delayed.run()
        assert self.flag == 5

    def testLoop(self):
        l = Looper()
        assert l.state == 0
        self.delayed.loop(l, ticks=0)
        assert l.state == 0
        self.delayed.run()
        assert l.state == 1
        for i in xrange(10):
            self.delayed.run()
        assert l.state == 5

    def bignum(self):
        self.setFlag(1111)

    def other(self):
        self.blah = 5
        
    def testEverything(self):
        self.delayed.loop(Looper())
        self.delayed.later(self.bignum, 5000)
        self.delayed.later(self.other, 1857)
        self.delayed.runEverything()
        assert self.flag == 1111, "number's wrong"


testCases = [DelayedTestCase]
