# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys, pickle

try:
    import threading
except ImportError:
    threading = None

from twisted.trial import unittest
from twisted.python import threadable
from twisted.internet import defer, reactor

class TestObject:
    synchronized = ['aMethod']

    x = -1
    y = 1

    def aMethod(self):
        for i in xrange(10):
            self.x, self.y = self.y, self.x
            self.z = self.x + self.y
            assert self.z == 0, "z == %d, not 0 as expected" % (self.z,)

threadable.synchronize(TestObject)

class SynchronizationTestCase(unittest.TestCase):
    def setUp(self):
        """
        Reduce the CPython check interval so that thread switches happen much
        more often, hopefully exercising more possible race conditions.  Also,
        delay actual test startup until the reactor has been started.
        """
        if hasattr(sys, 'getcheckinterval'):
            self.addCleanup(sys.setcheckinterval, sys.getcheckinterval())
            sys.setcheckinterval(7)
        # XXX This is a trial hack.  We need to make sure the reactor
        # actually *starts* for isInIOThread() to have a meaningful result.
        # Returning a Deferred here should force that to happen, if it has
        # not happened already.  In the future, this should not be
        # necessary.
        d = defer.Deferred()
        reactor.callLater(0, d.callback, None)
        return d


    def testIsInIOThread(self):
        foreignResult = []
        t = threading.Thread(target=lambda: foreignResult.append(threadable.isInIOThread()))
        t.start()
        t.join()
        self.failIf(foreignResult[0], "Non-IO thread reported as IO thread")
        self.failUnless(threadable.isInIOThread(), "IO thread reported as not IO thread")


    def testThreadedSynchronization(self):
        o = TestObject()

        errors = []

        def callMethodLots():
            try:
                for i in xrange(1000):
                    o.aMethod()
            except AssertionError, e:
                errors.append(str(e))

        threads = []
        for x in range(5):
            t = threading.Thread(target=callMethodLots)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if errors:
            raise unittest.FailTest(errors)

    def testUnthreadedSynchronization(self):
        o = TestObject()
        for i in xrange(1000):
            o.aMethod()

class SerializationTestCase(unittest.TestCase):
    def testPickling(self):
        lock = threadable.XLock()
        lockType = type(lock)
        lockPickle = pickle.dumps(lock)
        newLock = pickle.loads(lockPickle)
        self.failUnless(isinstance(newLock, lockType))

    def testUnpickling(self):
        lockPickle = 'ctwisted.python.threadable\nunpickle_lock\np0\n(tp1\nRp2\n.'
        lock = pickle.loads(lockPickle)
        newPickle = pickle.dumps(lock, 2)
        newLock = pickle.loads(newPickle)

if threading is None:
    SynchronizationTestCase.testThreadedSynchronization.skip = "Platform lacks thread support"
    SerializationTestCase.testPickling.skip = "Platform lacks thread support"
