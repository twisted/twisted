# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.threads._threadworker}.
"""

from twisted.trial.unittest import SynchronousTestCase

from .. import ThreadWorker

class FakeThread(object):
    """
    A fake L{threading.Thread}.

    @ivar target: A target function to run.
    @type target: L{callable}

    @ivar started: Has this thread been started?
    @type started: L{bool}
    """

    def __init__(self, target):
        """
        Create a L{FakeThread} with a target.
        """
        self.target = target
        self.started = False


    def start(self):
        """
        Set the "started" flag.
        """
        self.started = True



class FakeQueue(object):
    """
    A fake L{Queue} implementing.

    @ivar items: Items.
    @type items: L{list}
    """

    def __init__(self):
        """
        Create a L{FakeQueue}.
        """
        self.items = []


    def put(self, item):
        """
        Put an item into the queue for later retrieval by L{FakeQueue.get}.

        @param item: any object
        """
        self.items.append(item)


    def get(self):
        """
        Get an item.

        @return: an item previously put by C{put}.
        """
        return self.items.pop(0)



class ThreadWorkerTests(SynchronousTestCase):
    """
    Tests for L{ThreadWorker}
    """

    def test_startsThreadAndPerformsWork(self):
        """
        L{ThreadWorker} calls its C{createThread} callable to create a thread,
        its C{createQueue} callable to create a queue, and then the thread's
        target pulls work from that queue.
        """
        fakeThreads = []
        fakeQueue = FakeQueue()
        worker = ThreadWorker(lambda *a, **kw:
                              fakeThreads.append(FakeThread(*a, **kw)) or
                              fakeThreads[-1],
                              lambda: fakeQueue)
        self.assertEqual(len(fakeThreads), 1)
        self.assertEqual(fakeThreads[0].started, True)
        def doIt():
            doIt.done = True
        doIt.done = False
        worker.do(doIt)
        self.assertEqual(doIt.done, False)
        self.assertRaises(IndexError, fakeThreads[0].target)
        self.assertEqual(doIt.done, True)
