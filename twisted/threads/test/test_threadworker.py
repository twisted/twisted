# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.threads._threadworker}.
"""

from twisted.trial.unittest import SynchronousTestCase

from .. import ThreadWorker

class FakeQueueEmpty(Exception):
    """
    L{FakeQueue}'s C{get} has exhausted the queue.
    """


class FakeThread(object):
    """
    A fake L{threading.Thread}.

    @ivar target: A target function to run.
    @type target: L{callable}

    @ivar started: Has this thread been started?
    @type started: L{bool}

    @ivar joined: Has this thread been joined?
    @type joined: L{bool}
    """

    def __init__(self, target):
        """
        Create a L{FakeThread} with a target.
        """
        self.target = target
        self.started = False
        self.joined = False


    def start(self):
        """
        Set the "started" flag.
        """
        self.started = True


    def join(self):
        """
        Set the "joined" flag.
        """
        self.joined = True



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
        if not self.items:
            raise FakeQueueEmpty()
        return self.items.pop(0)




class ThreadWorkerTests(SynchronousTestCase):
    """
    Tests for L{ThreadWorker}.
    """

    def setUp(self):
        """
        Create a worker with fake threads.
        """
        self.fakeThreads = []
        self.fakeQueue = FakeQueue()
        self.worker = ThreadWorker(
            lambda *a, **kw:
            self.fakeThreads.append(FakeThread(*a, **kw)) or
            self.fakeThreads[-1],
            lambda: self.fakeQueue
        )


    def test_startsThreadAndPerformsWork(self):
        """
        L{ThreadWorker} calls its C{createThread} callable to create a thread,
        its C{createQueue} callable to create a queue, and then the thread's
        target pulls work from that queue.
        """
        self.assertEqual(len(self.fakeThreads), 1)
        self.assertEqual(self.fakeThreads[0].started, True)
        def doIt():
            doIt.done = True
        doIt.done = False
        self.worker.do(doIt)
        self.assertEqual(doIt.done, False)
        self.assertRaises(FakeQueueEmpty, self.fakeThreads[0].target)
        self.assertEqual(doIt.done, True)


    def test_quitJoinsThreads(self):
        """
        L{ThreadWorker.quit} joins all of its outstanding workers.
        """
        self.worker.do(lambda: None)
        self.worker.quit()
        self.assertEqual(len(self.fakeThreads), 1)
        self.assertEqual(self.fakeThreads[0].joined, True)
