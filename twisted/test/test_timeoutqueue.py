
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for timeoutqueue module.
"""

import time

from twisted.python import timeoutqueue
from twisted.trial import unittest, util
from twisted.internet import reactor, interfaces

timeoutqueueSuppression = util.suppress(
    message="timeoutqueue is deprecated since Twisted 8.0",
    category=DeprecationWarning)


class TimeoutQueueTest(unittest.TestCase):
    """
    Test L{timeoutqueue.TimeoutQueue} class.
    """

    def tearDown(self):
        del self.q

    def put(self):
        time.sleep(1)
        self.q.put(1)

    def test_timeout(self):
        q = self.q = timeoutqueue.TimeoutQueue()

        try:
            q.wait(1)
        except timeoutqueue.TimedOut:
            pass
        else:
            self.fail("Didn't time out")
    test_timeout.suppress = [timeoutqueueSuppression]

    def test_get(self):
        q = self.q = timeoutqueue.TimeoutQueue()

        start = time.time()
        threading.Thread(target=self.put).start()
        q.wait(1.5)
        assert time.time() - start < 2

        result = q.get(0)
        if result != 1:
            self.fail("Didn't get item we put in")
    test_get.suppress = [timeoutqueueSuppression]

    def test_deprecation(self):
        """
        Test that L{timeoutqueue.TimeoutQueue} prints a warning message.
        """
        def createQueue():
            return timeoutqueue.TimeoutQueue()
        self.q = self.assertWarns(
            DeprecationWarning,
            "timeoutqueue is deprecated since Twisted 8.0",
            __file__,
            createQueue)

    if interfaces.IReactorThreads(reactor, None) is None:
        test_get.skip = "No thread support, no way to test putting during a blocked get"
    else:
        global threading
        import threading

