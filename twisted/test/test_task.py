
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
Test cases for twisted.internet.task module.
"""

from pyunit import unittest
from twisted.internet import task, main


class Counter:
    index = 0
    
    def add(self):
        self.index += 1


class Order:

    stage = 0
    
    def a(self):
        if self.stage != 0: raise RuntimeError
        self.stage = 1
    
    def b(self):
        if self.stage != 1: raise RuntimeError
        self.stage = 2
    
    def c(self):
        if self.stage != 2: raise RuntimeError
        self.stage = 3
    

class TaskTestCase(unittest.TestCase):
    """Test the task scheduler."""
    
    def testScheduling(self):
        c = Counter()
        for i in range(100):
            task.schedule(c.add)
        for i in range(100):
            main.iterate()
        self.assertEquals(c.index, 100)
    
    def testCorrectOrder(self):
        o = Order()
        task.schedule(o.a)
        task.schedule(o.b)
        task.schedule(o.c)
        main.iterate()
        main.iterate()
        main.iterate()
        self.assertEquals(o.stage, 3)


testCases = [TaskTestCase]