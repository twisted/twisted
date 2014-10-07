# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the queue.
"""

from twisted.trial.unittest import SynchronousTestCase

import threading
from twisted.threads._fdq import PipeQueue

class QueueTests(SynchronousTestCase):
    """
    Tests for replacement-Queue implementation.
    """

    def makeQueue(self):
        """
        Create a queue, but clean it up.

        @return: a new L{PipeQueue}
        """
        q = PipeQueue()
        self.addCleanup(q.close)
        return q


    def test_putAndGet(self):
        """
        When one thread puts a value into a L{PipeQueue}, another thread can
        get it.
        """
        pq = self.makeQueue()
        values = []
        def oneget():
            values.append(pq.get())
        t = threading.Thread(target=oneget)
        t.start()
        pq.put(4321)
        t.join()
        self.assertEqual(values, [4321])
