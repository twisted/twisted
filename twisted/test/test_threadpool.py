# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import pickle, time

from twisted.trial import unittest
from twisted.python import log, threadable
from twisted.internet import reactor, interfaces

#
# See the end of this module for the remainder of the imports.
#

class Synchronization(object):
    failures = 0

    def __init__(self, N, waiting):
        self.N = N
        self.waiting = waiting
        self.lock = threading.Lock()
        self.runs = []

    def run(self):
        # This is the testy part: this is supposed to be invoked
        # serially from multiple threads.  If that is actually the
        # case, we will never fail to acquire this lock.  If it is
        # *not* the case, we might get here while someone else is
        # holding the lock.
        if self.lock.acquire(False):
            if not len(self.runs) % 5:
                time.sleep(0.0002) # Constant selected based on
                                   # empirical data to maximize the
                                   # chance of a quick failure if this
                                   # code is broken.
            self.lock.release()
        else:
            self.failures += 1

        # This is just the only way I can think of to wake up the test
        # method.  It doesn't actually have anything to do with the
        # test.
        self.lock.acquire()
        self.runs.append(None)
        if len(self.runs) == self.N:
            self.waiting.release()
        self.lock.release()

    synchronized = ["run"]
threadable.synchronize(Synchronization)



class ThreadPoolTestCase(unittest.TestCase):
    """Test threadpools."""

    def testPersistence(self):
        tp = threadpool.ThreadPool(7, 20)
        tp.start()

        # XXX Sigh - race condition: start should return a Deferred
        # which fires when all the workers it started have fully
        # started up.
        time.sleep(0.1)

        self.assertEquals(len(tp.threads), 7)
        self.assertEquals(tp.min, 7)
        self.assertEquals(tp.max, 20)

        # check that unpickled threadpool has same number of threads
        s = pickle.dumps(tp)
        tp2 = pickle.loads(s)
        tp2.start()

        # XXX As above
        time.sleep(0.1)

        self.assertEquals(len(tp2.threads), 7)
        self.assertEquals(tp2.min, 7)
        self.assertEquals(tp2.max, 20)

        tp.stop()
        tp2.stop()


    def _waitForLock(self, lock):
        for i in xrange(1000000):
            if lock.acquire(False):
                break
            time.sleep(1e-5)
        else:
            self.fail("A long time passed without succeeding")


    def _threadpoolTest(self, method):
        # This is a schizophrenic test: it seems to be trying to test
        # both the dispatch() behavior of the ThreadPool as well as
        # the serialization behavior of threadable.synchronize().  It
        # would probably make more sense as two much simpler tests.
        N = 10

        tp = threadpool.ThreadPool()
        tp.start()
        try:
            waiting = threading.Lock()
            waiting.acquire()
            actor = Synchronization(N, waiting)

            for i in xrange(N):
                tp.dispatch(actor, actor.run)

            self._waitForLock(waiting)

            self.failIf(actor.failures, "run() re-entered %d times" % (actor.failures,))
        finally:
            tp.stop()


    def testDispatch(self):
        return self._threadpoolTest(lambda tp, actor: tp.dispatch(actor, actor.run))


    def testCallInThread(self):
        return self._threadpoolTest(lambda tp, actor: tp.callInThread(actor.run))


    def testExistingWork(self):
        waiter = threading.Lock()
        waiter.acquire()

        tp = threadpool.ThreadPool(0, 1)
        tp.callInThread(waiter.release) # before start()
        tp.start()

        try:
            self._waitForLock(waiter)
        finally:
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
        self.event.wait(timeout=2)
        if not self.event.isSet():
            self.event.set()
            raise RuntimeError, "test failed"


    def testSingleThread(self):
        # Ensure no threads running
        self.assertEquals(self.threadpool.workers, 0)

        for i in range(10):
            self.threadpool.callInThread(self.event.set)
            self.event.wait()
            self.event.clear()

            # Ensure there are very few threads running
            self.failUnless(self.threadpool.workers <= 2)



if interfaces.IReactorThreads(reactor, None) is None:
    for cls in ThreadPoolTestCase, RaceConditionTestCase:
        setattr(cls, 'skip', "No thread support, nothing to test here")
else:
    import threading
    from twisted.python import threadpool
