
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
import threading, time


class Counter:
    index = 0
    
    def add(self):
        self.index = self.index + 1


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
    

class ThreadOrder(threading.Thread, Order):

    def run(self):
        self.schedule(self.a)
        self.schedule(self.b)
        self.schedule(self.c)


class TaskTestMixin:
    """Mixin for task scheduler tests."""
    
    def schedule(self, *args, **kwargs):
        """Override in subclasses."""
        raise NotImplentedError
    
    def testScheduling(self):
        c = Counter()
        for i in range(100):
            self.schedule(c.add)
        for i in range(100):
            main.iterate()
        self.assertEquals(c.index, 100)
    
    def testCorrectOrder(self):
        o = Order()
        self.schedule(o.a)
        self.schedule(o.b)
        self.schedule(o.c)
        main.iterate()
        main.iterate()
        main.iterate()
        self.assertEquals(o.stage, 3)
    
    def testNotRunAtOnce(self):
        c = Counter()
        self.schedule(c.add)
        # scheduled tasks should not be run at once:
        self.assertEquals(c.index, 0)
        main.iterate()
        self.assertEquals(c.index, 1)


class DefaultTaskTestCase(TaskTestMixin, unittest.TestCase):
    """Test the task.schedule scheduler."""
    
    def schedule(self, *args, **kwargs):
        apply(task.schedule, args, kwargs)


class ThreadedTaskTestCase(TaskTestMixin, unittest.TestCase):
    """Test the thread-safe task scheduler."""
    
    def setUp(self):
        self.scheduler = task.ThreadedScheduler()
        main.addDelayed(self.scheduler)
    
    def tearDown(self):
        main.removeDelayed(self.scheduler)
        del self.scheduler
    
    def schedule(self, *args, **kwargs):
        apply(self.scheduler.addTask, args, kwargs)


class NonThreadedTaskTestCase(TaskTestMixin, unittest.TestCase):
    """Test the non-thread-safe task scheduler."""
    
    def setUp(self):
        self.scheduler = task.Scheduler()
        main.addDelayed(self.scheduler)
    
    def tearDown(self):
        main.removeDelayed(self.scheduler)
        del self.scheduler
    
    def schedule(self, *args, **kwargs):
        apply(self.scheduler.addTask, args, kwargs)
    
    def testThreads(self):
        threads = []
        for i in range(10):
            t = ThreadOrder()
            t.schedule = self.schedule
            threads.append(t)
        for t in threads:
            t.start()
        main.iterate()
        time.sleep(0.1)
        main.iterate()
        main.iterate()
        for t in threads:
            self.assertEquals(t.stage, 3)

