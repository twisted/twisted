# -*- test-case-name: twisted.trial.test.test_util -*-
from twisted.python import failure, log
from twisted.python.runtime import platformType
from twisted.internet import defer, reactor, threads, interfaces
from twisted.trial import unittest, util, runner

# this is ok, the module has been designed for this usage
from twisted.trial.assertions import *

import os, time

class UserError(Exception):
    pass

class TestUserMethod(unittest.TestCase):
    def setUp(self):
        self.janitor = util._Janitor()

    def errorfulMethod(self):
        raise UserError, 'i am a user error'

    def errorfulDeferred(self):
        f = None
        try:
            self.errorfulMethod()
        except:
            f = failure.Failure()
        return defer.fail(f)

    def testErrorHandling(self):
        """wrapper around user code"""
        umw = runner.UserMethodWrapper(self.errorfulMethod, self.janitor)
        failUnlessRaises(runner.UserMethodError, umw)
        failUnless(umw.errors[0].check(UserError))
        failUnless(umw.endTime >= umw.startTime)

    def testDeferredError(self):
        umw = runner.UserMethodWrapper(self.errorfulDeferred, self.janitor)
        failUnlessRaises(runner.UserMethodError, umw)
        failUnless(umw.errors[0].check(UserError))
        failUnless(umw.endTime >= umw.startTime)


class WaitReentrancyTest(unittest.TestCase):

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = ("This test probably doesn't really need threads "
                "but hell if I can figure out how to rewrite it "
                "without them.  Skipping in the absence of "
                "thread-support.")

    def _returnedDeferredThenWait(self):
        def threadedOperation():
            time.sleep(0.1)
            return "Beginning"
        d = threads.deferToThread(threadedOperation)
        return d.addCallback(self._cbDoWait)

    def _cbDoWait(self, result):
        assertEquals(result, "Beginning")
        d = defer.Deferred()
        self.laterCall = reactor.callLater(0.1, d.callback, "End")
        assertEquals(unittest.wait(d), "End")

    def testReturnedDeferredThenWait(self):
        d = self._returnedDeferredThenWait()
        assertRaises(util.WaitIsNotReentrantError, unittest.wait, d)
        self.laterCall.cancel()

    def _reentrantWait(self):
        def threadedOperation(n):
            time.sleep(n)
            return n
        d1 = threads.deferToThread(threadedOperation, 0.125)
        d2 = threads.deferToThread(threadedOperation, 0.250)
        d1.addCallback(lambda ignored: unittest.wait(d2))
        unittest.wait(d1)

    def testReentrantWait(self):
        assertRaises(util.WaitIsNotReentrantError, self._reentrantWait)


class TestWait2(unittest.TestCase):
    NUM_FAILURES = 3

    def _generateFailure(self):
        try:
            raise RuntimeError, "i am a complete and utter failure"
        except RuntimeError:
            return failure.Failure()

    def _errorfulMethod(self):
        L = [self._generateFailure() for x in xrange(self.NUM_FAILURES)]
        raise util.MultiError(L)

    def testMultiError(self):
        assertRaises(util.MultiError, self._errorfulMethod)
        try:
            self._errorfulMethod()
        except util.MultiError, e:
            assert_(hasattr(e, 'failures'))
            assertEqual(len(e.failures), self.NUM_FAILURES)
            for f in e.failures:
                assert_(f.check(RuntimeError))

    def testMultiErrorAsFailure(self):
        assertRaises(util.MultiError, self._errorfulMethod)
        try:
            self._errorfulMethod()
        except util.MultiError:
            f = failure.Failure()
            assert_(hasattr(f, 'value'))
            assert_(hasattr(f.value, 'failures'))
            assertEqual(len(f.value.failures), self.NUM_FAILURES)
            for f in f.value.failures:
                assert_(f.check(RuntimeError))


class Attrib(object):
    foo = None

class AttributeSelection(unittest.TestCase):
    def testSelectFirstFound(self):
        a, b, c, d = Attrib(), Attrib(), Attrib(), Attrib()
        assertEqual(util._selectAttr('foo', a, b, c, d), None)
        d.foo = 'd_foo'
        assertEqual(util._selectAttr('foo', a, b, c, d), 'd_foo')
        c.foo = 'c_foo'
        assertEqual(util._selectAttr('foo', a, b, c, d), 'c_foo')
        b.foo = 'b_foo'
        assertEqual(util._selectAttr('foo', a, b, c, d), 'b_foo')
        a.foo = 'a_foo'
        assertEqual(util._selectAttr('foo', a, b, c, d), 'a_foo')


class TestMktemp(unittest.TestCase):
    def testMktmp(self):
        tmp = self.mktemp()
        tmp1 = self.mktemp()
        exp = os.path.join('twisted.trial.test.test_trial', 'UtilityTestCase', 'testMktmp')
        failIfEqual(tmp, tmp1)
        failIf(os.path.exists(exp))


class TestWaitInterrupt(unittest.TestCase):
    def testKeyboardInterrupt(self):
        # Test the KeyboardInterrupt is *not* caught by wait -- we
        # want to allow users to Ctrl-C test runs.  And the use of the
        # useWaitError should not matter in this case.
        def raiseKeyInt(ignored):
            raise KeyboardInterrupt, "Simulate user hitting Ctrl-C"

        d = defer.Deferred()
        d.addCallback(raiseKeyInt)
        reactor.callLater(0, d.callback, True)
        self.assertRaises(KeyboardInterrupt, util.wait, d, useWaitError=False)

        d = defer.Deferred()
        d.addCallback(raiseKeyInt)
        reactor.callLater(0, d.callback, True)
        self.assertRaises(KeyboardInterrupt, util.wait, d, useWaitError=True)


# glyph's contributed test
# http://twistedmatrix.com/bugs/file317/failing.py

class FakeException(Exception):
    pass

def die():
    try:
        raise FakeException()
    except:
        log.err()

class MyTest(unittest.TestCase):
    def testFlushAfterWait(self):
        die()
        util.wait(defer.succeed(''))
        log.flushErrors(FakeException)

    def testFlushByItself(self):
        die()
        log.flushErrors(FakeException)

