
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
        


testCases = [DelayedTestCase]
