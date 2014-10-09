# -*- test-case-name: twisted.threads.test.test_threadworker -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of an L{IWorker} based on native threads and queues.
"""

from zope.interface import implementer
from ._ithreads import IWorker
from ._convenience import Quit


_stop = object()

@implementer(IWorker)
class ThreadWorker(object):
    """
    An L{IWorker} implemented based on a thread and a queue.
    """

    def __init__(self, createThread, createQueue):
        """
        @param createThread: create a L{threading.Thread} to perform work on.
        @type createThread: 1-argument callable taking a 0-argument callablea
            and returning a L{thrreading.Thread}

        @param createQueue: Create an object like a L{Queue.Queue}, with C{put}
            and C{get} methods.
        @param createQueue: 0-argument callable returning a L{Queue.Queue}
        """
        self._q = createQueue()
        def work():
            for task in iter(self._q.get, _stop):
                task()
        self._thread = createThread(work)
        self._thread.start()
        self._hasQuit = Quit()


    def do(self, task):
        """
        Perform the given task on a thread.

        @param task: the function to call on a thread.
        """
        self._hasQuit.check()
        self._q.put(task)


    def quit(self):
        """
        Reject all future work and stop the thread started by C{__init__}.
        """
        # Reject all future work.  Set this _before_ enqueueing _stop, so
        # that no work is ever enqueued _after_ _stop.
        self._hasQuit.set()
        self._q.put(_stop)
        try:
            self._thread.join()
        except RuntimeError:
            pass



