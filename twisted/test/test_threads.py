# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test methods in twisted.internet.threads and reactor thread APIs."""

import time, sys

from twisted.trial import unittest

from twisted.internet import reactor, interfaces, threads
from twisted.python import failure, threadable

class Counter:    
    index = 0
    problem = 0
    
    def sync_add(self):
        """A thread-safe method."""
        self.add()

    def add(self):
        """A non thread-safe method."""
        next = self.index + 1
        # another thread could jump in here and increment self.index on us
        if next != self.index + 1:
            self.problem = 1
            raise ValueError
        # or here, same issue but we wouldn't catch it. We'd overwrite their
        # results, and the index will have lost a count. If several threads
        # get in here, we will actually make the count go backwards when we
        # overwrite it.
        self.index = next
    
    synchronized = ["sync_add"]
threadable.synchronize(Counter)


class ThreadsTestCase(unittest.TestCase):
    """Test twisted.internet.threads."""

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = "No thread support, nothing to test here"

    def setUp(self):
        reactor.suggestThreadPoolSize(8)
    def tearDown(self):
        reactor.suggestThreadPoolSize(0)

    def testCallInThread(self):
        c = Counter()
        
        for i in range(1000):
            reactor.callInThread(c.sync_add)

        # those thousand calls should all be running "at the same time" (at
        # least up to the size of the thread pool, anyway). While they are
        # fighting over the right to add, watch carefully for any sign of
        # overlapping threads, which might be detected by the thread itself
        # (c.problem), or might appear as an index that doesn't go all the
        # way up to 1000 (a few missing counts and it could stop at 999). If
        # threadpools are really broken, it might never increment at all.

        # in practice, if the threads are running unsynchronized (say, using
        # c.add instead of c.sync_add), it takes about 10 repetitions of
        # this test case to expose a problem
        
        when = time.time()
        oldIndex = 0
        while c.index < 1000:
            # watch for the count to go backwards
            assert oldIndex <= c.index
            # spend some extra time per loop making sure we eventually get
            # out of it
            self.failIf(c.problem, "threads reported overlap")
            if c.index > oldIndex:
                when = time.time() # reset each count
            else:
                if time.time() > when + 5:
                    if c.index > 0:
                        self.fail("threads lost a count, index is %d "
                                  " time is %s, when is %s" %
                                  (c.index, time.time(), when))
                    else:
                        self.fail("threads never started")
            oldIndex = c.index

        # This check will never fail, because a missing count wouldn't make
        # it out of the 'while c.index < 1000' loop. But it makes it clear
        # what our expectation are.
        self.assertEquals(c.index, 1000, "threads lost a count")

    if sys.version.find("freebsd") != -1:
        testCallInThread.todo = "this test fails on freebsd - slyphon"

    def testCallMultiple(self):
        c = Counter()
        # we call the non-thread safe method, but because they should
        # all be called in same thread, this is ok.
        commands = [(c.add, (), {})] * 1000
        threads.callMultipleInThread(commands)

        when = time.time()
        oldIndex = 0
        while c.index < 1000:
            assert oldIndex <= c.index
            self.failIf(c.problem, "threads reported overlap")
            if c.index > oldIndex:
                when = time.time() # reset each count
            else:
                if time.time() > when + 5:
                    if c.index > 0:
                        self.fail("threads lost a count")
                    else:
                        self.fail("threads never started")
            oldIndex = c.index
        
        self.assertEquals(c.index, 1000)
    
    def testSuggestThreadPoolSize(self):
        reactor.suggestThreadPoolSize(34)
        reactor.suggestThreadPoolSize(4)

class DeferredResultTestCase(unittest.TestCase):
    """Test threads.deferToThread"""

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = "No thread support, nothing to test here"

    def setUp(self):
        reactor.suggestThreadPoolSize(8)

    def tearDown(self):
        reactor.suggestThreadPoolSize(0)


    def testDeferredResult(self):
        d = threads.deferToThread(lambda x, y=5: x + y, 3, y=4)
        d.addCallback(self.assertEquals, 7)
        return d

    def testDeferredFailure(self):
        class NewError(Exception):
            pass
        def raiseError():
            raise NewError
        d = threads.deferToThread(raiseError)
        return self.assertFailure(d, NewError)

    def testDeferredFailure2(self):
        # set up a condition that causes cReactor to hang. These conditions
        # can also be set by other tests when the full test suite is run in
        # alphabetical order (test_flow.FlowTest.testThreaded followed by
        # test_internet.ReactorCoreTestCase.testStop, to be precise). By
        # setting them up explicitly here, we can reproduce the hang in a
        # single precise test case instead of depending upon side effects of
        # other tests.
        #
        # alas, this test appears to flunk the default reactor too
        
        def nothing(): pass
        reactor.callLater(1, reactor.crash)
        reactor.callInThread(nothing)
        reactor.run()

        def raiseError(): raise TypeError
        d = threads.deferToThread(raiseError)
        d.addCallbacks(lambda res: self.fail("should have failed"),
                       self._checkTypeError)
        return d
    testDeferredFailure2.timeout = 1

    def _checkTypeError(self, error):
        self.assert_( isinstance(error, failure.Failure) )
        self.assertEquals(error.type, TypeError)
