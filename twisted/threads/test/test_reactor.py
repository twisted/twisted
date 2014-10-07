# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for integration with L{twisted.internet}.
"""

from twisted.trial.unittest import SynchronousTestCase

from .. import ReactorWorker

class FakePartialReactorThreads(object):
    """
    Implement only callFromThread.
    """

    def __init__(self):
        """
        Calls.
        """
        self._calls = []


    def callFromThread(self, f, *a, **kw):
        """
        Enqueue a call for later.

        @param f: the function to call

        @param a: the arguments to call it with

        @param kw: the keyword args to call it with
        """
        self._calls.append((f, a, kw))


    def flushCalls(self):
        """
        Call all the calls enqueued by callFromThread.
        """
        while self._calls:
            f, a, k = self._calls.pop(0)
            f(*a, **k)


    def stop(self):
        """
        Stop the reactor.
        """
        self.stopped = False



class ReactorWorkerTests(SynchronousTestCase):
    """
    Tests for L{ReactorWorker}
    """

    def test_doCallsFromThread(self):
        """
        L{ReactorWorker.do} calls the given function with C{callFromThread}.
        """
        reactor = FakePartialReactorThreads()
        worker = ReactorWorker(reactor)
        later = []
        def work():
            work.wasLater = bool(later)
        worker.do(work)
        later.append(True)
        reactor.flushCalls()
        self.assertEqual(work.wasLater, True)
