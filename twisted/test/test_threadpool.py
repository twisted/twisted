
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
import pickle, time, threading

from twisted.python import threadpool, threadable, log


class Counter(log.Logger):    
    index = 0
    
    def add(self):
        self.index = self.index + 1
    
    synchronized = ["add"]

threadable.synchronize(Counter)


class ThreadPoolTestCase(unittest.TestCase):
    """Test threadpools."""

    def testPersistence(self):
        tp = threadpool.ThreadPool(7, 20)
        tp.start()
        time.sleep(0.1)
        self.assertEquals(len(tp.threads), 7)
        self.assertEquals(tp.min, 7)
        self.assertEquals(tp.max, 20)
        
        # check that unpickled threadpool has same number of threads
        s = pickle.dumps(tp)
        tp2 = pickle.loads(s)
        tp2.start()
        time.sleep(0.1)
        self.assertEquals(len(tp2.threads), 7)
        self.assertEquals(tp2.min, 7)
        self.assertEquals(tp2.max, 20)
        
        tp.stop()
        tp2.stop()

    def testCounter(self):
        tp = threadpool.ThreadPool()
        tp.start()
        c = Counter()
        
        for i in range(1000):
            tp.dispatch(c, c.add)
        
        oldIndex = 0
        while c.index < 1000:
            assert oldIndex <= c.index
            oldIndex = c.index
        
        self.assertEquals(c.index, 1000)
        tp.stop()

    def testExistingWork(self):
        done = []
        def work(): done.append(1)
        tp = threadpool.ThreadPool(0, 1)
        tp.callInThread(work) # before start()
        tp.start()
        while not done: pass
        tp.stop()


class RaceConditionTestCase(unittest.TestCase):

    def setUp(self):
        self.event = threading.Event()
        self.threadpool = threadpool.ThreadPool(0, 10)
        self.threadpool.start()
    
    def tearDown(self):
        del self.event
        self.threadpool.stop()
        del self.threadpool
    
    def testRace(self):
        self.threadpool.callInThread(self.event.set)
        self.event.wait()
        self.event.clear()
        for i in range(3):
            self.threadpool.callInThread(self.event.wait)
        self.threadpool.callInThread(self.event.set)
        time.sleep(2)
        if not self.event.isSet():
            self.event.set()
            raise RuntimeError, "test failed"
