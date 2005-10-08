import StringIO
from twisted.internet import defer
from twisted.trial import unittest
from twisted.trial import runner, reporter, util
from twisted.trial.test import detests


class TestSetUp(unittest.TestCase):
    def _loadSuite(self, klass):
        loader = runner.TestLoader()
        r = reporter.Reporter(stream=StringIO.StringIO())
        s = loader.loadClass(klass)
        return r, s

    def test_success(self):
        result, suite = self._loadSuite(detests.DeferredSetUpOK)
        suite(result)
        self.failUnless(result.wasSuccessful())
        self.failUnlessEqual(result.testsRun, 1)

    def test_fail(self):
        self.failIf(detests.DeferredSetUpFail.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpFail)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.failUnlessEqual(result.testsRun, 1)
        self.failUnlessEqual(len(result.failures), 1)
        self.failUnlessEqual(len(result.errors), 0)
        self.failIf(detests.DeferredSetUpFail.testCalled)

    def test_callbackFail(self):
        self.failIf(detests.DeferredSetUpCallbackFail.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpCallbackFail)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.failUnlessEqual(result.testsRun, 1)
        self.failUnlessEqual(len(result.failures), 1)
        self.failUnlessEqual(len(result.errors), 0)
        self.failIf(detests.DeferredSetUpCallbackFail.testCalled)
        
    def test_error(self):
        self.failIf(detests.DeferredSetUpError.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpError)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.failUnlessEqual(result.testsRun, 1)
        self.failUnlessEqual(len(result.failures), 0)
        self.failUnlessEqual(len(result.errors), 1)
        self.failIf(detests.DeferredSetUpError.testCalled)

    def test_skip(self):
        self.failIf(detests.DeferredSetUpSkip.testCalled)
        result, suite = self._loadSuite(detests.DeferredSetUpSkip)
        suite(result)
        self.failUnless(result.wasSuccessful())
        self.failUnlessEqual(result.testsRun, 1)
        self.failUnlessEqual(len(result.failures), 0)
        self.failUnlessEqual(len(result.errors), 0)
        self.failUnlessEqual(len(result.skips), 1)
        self.failIf(detests.DeferredSetUpSkip.testCalled)
        self.failUnlessEqual(str(result.skips[0][1]), 'skip me')
        

class TestNeverFire(unittest.TestCase):
    def setUp(self):
        self._oldTimeout = util.DEFAULT_TIMEOUT_DURATION
        util.DEFAULT_TIMEOUT_DURATION = 0.1

    def tearDown(self):
        util.DEFAULT_TIMEOUT_DURATION = self._oldTimeout

    def _loadSuite(self, klass):
        loader = runner.TestLoader()
        r = reporter.Reporter(stream=StringIO.StringIO())
        s = loader.loadClass(klass)
        return r, s

    def test_setUp(self):
        self.failIf(detests.DeferredSetUpNeverFire.testCalled)        
        result, suite = self._loadSuite(detests.DeferredSetUpNeverFire)
        suite(result)
        self.failIf(result.wasSuccessful())
        self.failUnlessEqual(result.testsRun, 1)
        self.failUnlessEqual(len(result.failures), 0)
        self.failUnlessEqual(len(result.errors), 1)
        self.failIf(detests.DeferredSetUpNeverFire.testCalled)
        self.failUnless(result.errors[0][1].check(defer.TimeoutError))
