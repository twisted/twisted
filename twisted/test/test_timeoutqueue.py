
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for timeoutqueue module.
"""

import time

from twisted.trial import unittest
from twisted.python import timeoutqueue
from twisted.internet import reactor, interfaces

class TimeoutQueueTest(unittest.TestCase):
    
    def setUp(self):
        self.q = timeoutqueue.TimeoutQueue()
    
    def tearDown(self):
        del self.q
    
    def put(self):
        time.sleep(1)
        self.q.put(1)
        
    def testTimeout(self):
        q = self.q

        try:
            q.wait(1)
        except timeoutqueue.TimedOut:
            pass
        else:
            raise AssertionError, "didn't time out"

    def testGet(self):
        q = self.q
        start = time.time()
        threading.Thread(target=self.put).start()
        q.wait(1.5)
        assert time.time() - start < 2

        result = q.get(0)
        if result != 1:
            raise AssertionError, "didn't get item we put in"

    if interfaces.IReactorThreads(reactor, None) is None:
        testGet.skip = "No thread support, no way to test putting during a blocked get"
    else:
        global threading
        import threading
