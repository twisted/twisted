# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for returning Deferreds from a TestCase.
"""

from __future__ import division, absolute_import

import unittest as pyunit

from twisted.internet import defer
from twisted.trial import unittest, reporter
from twisted.trial import util
from twisted.trial.test import detests


class TestSetUp(unittest.TestCase):
    def _loadSuite(self, klass):
        loader = pyunit.TestLoader()
        r = reporter.TestResult()
        s = loader.loadTestsFromTestCase(klass)
        return r, s

    def test_success(self):
        result, suite = self._loadSuite(detests.DeferredSetUpOK)
        suite(result)
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_fail(self):
        self.failIf(detests.DeferredSetUpFail.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpFail)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.failIf(detests.DeferredSetUpFail.testCalled)

    def test_callbackFail(self):
        self.failIf(detests.DeferredSetUpCallbackFail.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpCallbackFail)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.failIf(detests.DeferredSetUpCallbackFail.testCalled)

    def test_error(self):
        self.failIf(detests.DeferredSetUpError.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpError)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.failIf(detests.DeferredSetUpError.testCalled)

    def test_skip(self):
        self.failIf(detests.DeferredSetUpSkip.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpSkip)
        suite(result)
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.skips), 1)
        self.failIf(detests.DeferredSetUpSkip.testCalled)


class TestNeverFire(unittest.TestCase):
    def setUp(self):
        self._oldTimeout = util.DEFAULT_TIMEOUT_DURATION
        util.DEFAULT_TIMEOUT_DURATION = 0.1

    def tearDown(self):
        util.DEFAULT_TIMEOUT_DURATION = self._oldTimeout

    def _loadSuite(self, klass):
        loader = pyunit.TestLoader()
        r = reporter.TestResult()
        s = loader.loadTestsFromTestCase(klass)
        return r, s

    def test_setUp(self):
        self.failIf(detests.DeferredSetUpNeverFire.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpNeverFire)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.failIf(detests.DeferredSetUpNeverFire.testCalled)
        self.failUnless(result.errors[0][1].check(defer.TimeoutError))


class TestTester(unittest.TestCase):
    def getTest(self, name):
        raise NotImplementedError("must override me")

    def runTest(self, name):
        result = reporter.TestResult()
        self.getTest(name).run(result)
        return result


class TestDeferred(TestTester):
    def getTest(self, name):
        return detests.DeferredTests(name)

    def test_pass(self):
        result = self.runTest('test_pass')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_passGenerated(self):
        result = self.runTest('test_passGenerated')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.failUnless(detests.DeferredTests.touched)

    def test_fail(self):
        result = self.runTest('test_fail')
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)

    def test_failureInCallback(self):
        result = self.runTest('test_failureInCallback')
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)

    def test_errorInCallback(self):
        result = self.runTest('test_errorInCallback')
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)

    def test_skip(self):
        result = self.runTest('test_skip')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.skips), 1)
        self.failIf(detests.DeferredTests.touched)

    def test_todo(self):
        result = self.runTest('test_expectedFailure')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.expectedFailures), 1)

    def test_thread(self):
        result = self.runTest('test_thread')
        self.assertEqual(result.testsRun, 1)
        self.failUnless(result.wasSuccessful(), result.errors)



class TestTimeout(TestTester):
    def getTest(self, name):
        return detests.TimeoutTests(name)

    def _wasTimeout(self, error):
        self.assertEqual(error.check(defer.TimeoutError),
                             defer.TimeoutError)

    def test_pass(self):
        result = self.runTest('test_pass')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_passDefault(self):
        result = self.runTest('test_passDefault')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_timeout(self):
        result = self.runTest('test_timeout')
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        self._wasTimeout(result.errors[0][1])

    def test_timeoutZero(self):
        result = self.runTest('test_timeoutZero')
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        self._wasTimeout(result.errors[0][1])

    def test_skip(self):
        result = self.runTest('test_skip')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.skips), 1)

    def test_todo(self):
        result = self.runTest('test_expectedFailure')
        self.failUnless(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.expectedFailures), 1)
        self._wasTimeout(result.expectedFailures[0][1])

    def test_errorPropagation(self):
        result = self.runTest('test_errorPropagation')
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self._wasTimeout(detests.TimeoutTests.timedOut)

    def test_classTimeout(self):
        loader = pyunit.TestLoader()
        suite = loader.loadTestsFromTestCase(detests.TestClassTimeoutAttribute)
        result = reporter.TestResult()
        suite.run(result)
        self.assertEqual(len(result.errors), 1)
        self._wasTimeout(result.errors[0][1])

    def test_callbackReturnsNonCallingDeferred(self):
        #hacky timeout
        # raises KeyboardInterrupt because Trial sucks
        from twisted.internet import reactor
        call = reactor.callLater(2, reactor.crash)
        result = self.runTest('test_calledButNeverCallback')
        if call.active():
            call.cancel()
        self.failIf(result.wasSuccessful())
        self._wasTimeout(result.errors[0][1])


# The test loader erroneously attempts to run this:
del TestTester
