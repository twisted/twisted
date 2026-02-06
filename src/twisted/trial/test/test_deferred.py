# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for returning Deferreds from a TestCase.
"""
from __future__ import annotations

import unittest as pyunit

from twisted.internet import defer
from twisted.python.failure import Failure
from twisted.trial import reporter, unittest, util
from twisted.trial.test import detests


class SetUpTests(unittest.TestCase):
    def _loadSuite(
        self, klass: type[pyunit.TestCase]
    ) -> tuple[reporter.TestResult, pyunit.TestSuite]:
        loader = pyunit.TestLoader()
        r = reporter.TestResult()
        s = loader.loadTestsFromTestCase(klass)
        return r, s

    def test_success(self) -> None:
        result, suite = self._loadSuite(detests.DeferredSetUpOK)
        suite(result)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_fail(self) -> None:
        self.assertFalse(detests.DeferredSetUpFail.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpFail)
        suite(result)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.assertFalse(detests.DeferredSetUpFail.testCalled)

    def test_callbackFail(self) -> None:
        self.assertFalse(detests.DeferredSetUpCallbackFail.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpCallbackFail)
        suite(result)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.assertFalse(detests.DeferredSetUpCallbackFail.testCalled)

    def test_error(self) -> None:
        self.assertFalse(detests.DeferredSetUpError.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpError)
        suite(result)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.assertFalse(detests.DeferredSetUpError.testCalled)

    def test_skip(self) -> None:
        self.assertFalse(detests.DeferredSetUpSkip.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpSkip)
        suite(result)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.skips), 1)
        self.assertFalse(detests.DeferredSetUpSkip.testCalled)


class NeverFireTests(unittest.TestCase):
    def setUp(self) -> None:
        self._oldTimeout = util.DEFAULT_TIMEOUT_DURATION
        util.DEFAULT_TIMEOUT_DURATION = 0.1

    def tearDown(self) -> None:
        util.DEFAULT_TIMEOUT_DURATION = self._oldTimeout

    def _loadSuite(
        self, klass: type[pyunit.TestCase]
    ) -> tuple[reporter.TestResult, pyunit.TestSuite]:
        loader = pyunit.TestLoader()
        r = reporter.TestResult()
        s = loader.loadTestsFromTestCase(klass)
        return r, s

    def test_setUp(self) -> None:
        self.assertFalse(detests.DeferredSetUpNeverFire.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpNeverFire)
        suite(result)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 1)
        self.assertFalse(detests.DeferredSetUpNeverFire.testCalled)
        assert isinstance(result.errors[0][1], Failure)
        self.assertTrue(result.errors[0][1].check(defer.TimeoutError))


class TestTester(unittest.TestCase):
    def getTest(self, name: str) -> pyunit.TestCase:
        raise NotImplementedError("must override me")

    def runTest(self, name: str) -> reporter.TestResult:  # type: ignore[override]
        result = reporter.TestResult()
        self.getTest(name).run(result)
        return result


class DeferredTests(TestTester):
    def getTest(self, name: str) -> detests.DeferredTests:
        return detests.DeferredTests(name)

    def test_pass(self) -> None:
        result = self.runTest("test_pass")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_passInlineCallbacks(self) -> None:
        """
        The body of a L{defer.inlineCallbacks} decorated test gets run.
        """
        result = self.runTest("test_passInlineCallbacks")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(detests.DeferredTests.touched)

    def test_fail(self) -> None:
        result = self.runTest("test_fail")
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)

    def test_failureInCallback(self) -> None:
        result = self.runTest("test_failureInCallback")
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)

    def test_errorInCallback(self) -> None:
        result = self.runTest("test_errorInCallback")
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)

    def test_skip(self) -> None:
        result = self.runTest("test_skip")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.skips), 1)
        self.assertFalse(detests.DeferredTests.touched)

    def test_todo(self) -> None:
        result = self.runTest("test_expectedFailure")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.expectedFailures), 1)

    def test_thread(self) -> None:
        result = self.runTest("test_thread")
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful(), result.errors)


class TimeoutTests(TestTester):
    def getTest(self, name: str) -> detests.TimeoutTests:
        return detests.TimeoutTests(name)

    def _wasTimeout(self, error: Failure, expectedMessage: str) -> None:
        self.assertEqual(error.check(defer.TimeoutError), defer.TimeoutError)
        self.assertIn(expectedMessage, error.value.args[0])

    def test_pass(self) -> None:
        result = self.runTest("test_pass")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_passDefault(self) -> None:
        result = self.runTest("test_passDefault")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_timeout(self) -> None:
        result = self.runTest("test_timeout")
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        assert isinstance(result.errors[0][1], Failure)
        self._wasTimeout(
            result.errors[0][1], "(test_timeout) still running at 0.1 secs"
        )

    def test_timeoutZero(self) -> None:
        result = self.runTest("test_timeoutZero")
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        assert isinstance(result.errors[0][1], Failure)
        self._wasTimeout(
            result.errors[0][1], "(test_timeoutZero) still running at 0.0 secs"
        )

    def test_addCleanupPassDefault(self) -> None:
        """
        See L{twisted.trial.test.detests.TimeoutTests.test_addCleanupPassDefault}
        """
        result = self.runTest("test_addCleanupPassDefault")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_addCleanupTimeout(self) -> None:
        """
        See L{twisted.trial.test.detests.TimeoutTests.test_addCleanupTimeout}

        TODO: current test does not mock reactor and thus the test spends real time
        until the timeout fires.
        """
        result = self.runTest("test_addCleanupTimeout")
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        assert isinstance(result.errors[0][1], Failure)
        self._wasTimeout(
            result.errors[0][1], "(cleanup function cleanup) still running at 0.1 secs"
        )

    def test_skip(self) -> None:
        result = self.runTest("test_skip")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.skips), 1)

    def test_todo(self) -> None:
        result = self.runTest("test_expectedFailure")
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.expectedFailures), 1)
        assert isinstance(result.expectedFailures[0][1], Failure)
        self._wasTimeout(
            result.expectedFailures[0][1],
            "(test_expectedFailure) still running at 0.1 secs",
        )

    def test_errorPropagation(self) -> None:
        result = self.runTest("test_errorPropagation")
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        assert detests.TimeoutTests.timedOut is not None
        self._wasTimeout(
            detests.TimeoutTests.timedOut,
            "(test_errorPropagation) still running at 0.1 secs",
        )

    def test_classTimeout(self) -> None:
        loader = pyunit.TestLoader()
        suite = loader.loadTestsFromTestCase(detests.TestClassTimeoutAttribute)
        result = reporter.TestResult()
        suite.run(result)
        self.assertEqual(len(result.errors), 1)
        assert isinstance(result.errors[0][1], Failure)
        self._wasTimeout(result.errors[0][1], "(testMethod) still running at 0.2 secs")

    def test_callbackReturnsNonCallingDeferred(self) -> None:
        # hacky timeout
        # raises KeyboardInterrupt because Trial sucks
        from twisted.internet import reactor

        call = reactor.callLater(2, reactor.crash)  # type: ignore[attr-defined]
        result = self.runTest("test_calledButNeverCallback")
        if call.active():
            call.cancel()
        self.assertFalse(result.wasSuccessful())
        assert isinstance(result.errors[0][1], Failure)
        self._wasTimeout(
            result.errors[0][1],
            "(test_calledButNeverCallback) still running at 0.1 secs",
        )


# The test loader erroneously attempts to run this:
del TestTester
