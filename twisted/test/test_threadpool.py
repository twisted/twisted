# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


import pickle, time, weakref, gc

from twisted.trial import unittest, util
from twisted.python import threadable
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
    """
    Test threadpools.
    """

    def test_threadCreationArguments(self):
        """
        Test that creating threads in the threadpool with application-level
        objects as arguments doesn't results in those objects never being
        freed, with the thread maintaining a reference to them as long as it
        exists.
        """
        try:
            tp = threadpool.ThreadPool(0, 1)
            tp.start()

            # Sanity check - no threads should have been started yet.
            self.assertEqual(tp.threads, [])

            # Here's our function
            def worker(arg):
                pass
            # weakref need an object subclass
            class Dumb(object):
                pass
            # And here's the unique object
            unique = Dumb()

            workerRef = weakref.ref(worker)
            uniqueRef = weakref.ref(unique)

            # Put some work in
            tp.callInThread(worker, unique)

            # Add an event to wait completion
            event = threading.Event()
            tp.callInThread(event.set)
            event.wait(self.getTimeout())

            del worker
            del unique
            gc.collect()
            self.assertEquals(uniqueRef(), None)
            self.assertEquals(workerRef(), None)
        finally:
            tp.stop()


    def test_persistence(self):
        """
        Threadpools can be pickled and unpickled, which should preserve the
        number of threads and other parameters.
        """
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
        """
        Test synchronization of calls made with C{method}, which should be
        one of the mecanisms of the threadpool to execute work in threads.
        """
        # This is a schizophrenic test: it seems to be trying to test
        # both the callInThread()/dispatch() behavior of the ThreadPool as well
        # as the serialization behavior of threadable.synchronize().  It
        # would probably make more sense as two much simpler tests.
        N = 10

        tp = threadpool.ThreadPool()
        tp.start()
        try:
            waiting = threading.Lock()
            waiting.acquire()
            actor = Synchronization(N, waiting)

            for i in xrange(N):
                method(tp, actor)

            self._waitForLock(waiting)

            self.failIf(actor.failures, "run() re-entered %d times" %
                                        (actor.failures,))
        finally:
            tp.stop()


    def test_dispatch(self):
        """
        Call C{_threadpoolTest} with C{dispatch}.
        """
        return self._threadpoolTest(
            lambda tp, actor: tp.dispatch(actor, actor.run))

    test_dispatch.suppress = [util.suppress(
                message="dispatch\(\) is deprecated since Twisted 8.0, "
                        "use callInThread\(\) instead",
                category=DeprecationWarning)]


    def test_callInThread(self):
        """
        Call C{_threadpoolTest} with C{callInThread}.
        """
        return self._threadpoolTest(
            lambda tp, actor: tp.callInThread(actor.run))


    def test_existingWork(self):
        """
        Work added to the threadpool before its start should be executed once
        the threadpool is started: this is ensured by trying to release a lock
        previously acquired.
        """
        waiter = threading.Lock()
        waiter.acquire()

        tp = threadpool.ThreadPool(0, 1)
        tp.callInThread(waiter.release) # before start()
        tp.start()

        try:
            self._waitForLock(waiter)
        finally:
            tp.stop()


    def test_dispatchDeprecation(self):
        """
        Test for the deprecation of the dispatch method.
        """
        tp = threadpool.ThreadPool()
        tp.start()
        def cb():
            return tp.dispatch(None, lambda: None)
        try:
            self.assertWarns(DeprecationWarning,
                "dispatch() is deprecated since Twisted 8.0, "
                "use callInThread() instead",
                __file__, cb)
        finally:
            tp.stop()


    def test_dispatchWithCallbackDeprecation(self):
        """
        Test for the deprecation of the dispatchWithCallback method.
        """
        tp = threadpool.ThreadPool()
        tp.start()
        def cb():
            return tp.dispatchWithCallback(
                None,
                lambda x: None,
                lambda x: None,
                lambda: None)
        try:
            self.assertWarns(DeprecationWarning,
                "dispatchWithCallback() is deprecated since Twisted 8.0, "
                "use twisted.internet.threads.deferToThread() instead.",
                __file__, cb)
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


    def test_synchronization(self):
        """
        Test a race condition: ensure that actions run in the pool synchronize
        with actions run in the main thread.
        """
        timeout = self.getTimeout()
        self.threadpool.callInThread(self.event.set)
        self.event.wait(timeout)
        self.event.clear()
        for i in range(3):
            self.threadpool.callInThread(self.event.wait)
        self.threadpool.callInThread(self.event.set)
        self.event.wait(timeout)
        if not self.event.isSet():
            self.event.set()
            self.fail("Actions not synchronized")


    def test_singleThread(self):
        """
        Test that the creation of new threads in the pool occurs only when
        more jobs are added and all existing threads are occupied.
        """
        # Ensure no threads running
        self.assertEquals(self.threadpool.workers, 0)
        timeout = self.getTimeout()
        for i in range(10):
            self.threadpool.callInThread(self.event.set)
            self.event.wait(timeout)
            self.event.clear()

            # Ensure there are very few threads running
            self.failUnless(self.threadpool.workers <= 2)



if interfaces.IReactorThreads(reactor, None) is None:
    for cls in ThreadPoolTestCase, RaceConditionTestCase:
        setattr(cls, 'skip', "No thread support, nothing to test here")
else:
    import threading
    from twisted.python import threadpool

