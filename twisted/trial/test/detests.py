from twisted.trial import unittest
from twisted.internet import defer


class DeferredSetUpOK(unittest.TestCase):
    def setUp(self):
        d = defer.succeed('value')
        d.addCallback(self._cb_setUpCalled)
        return d

    def _cb_setUpCalled(self, ignored):
        self._setUpCalled = True

    def test_ok(self):
        self.failUnless(self._setUpCalled)


class DeferredSetUpFail(unittest.TestCase):
    testCalled = False
    
    def setUp(self):
        return defer.fail(unittest.FailTest('i fail'))

    def test_ok(self):
        DeferredSetUpFail.testCalled = True
        self.fail("I should not get called")


class DeferredSetUpCallbackFail(unittest.TestCase):
    testCalled = False
    
    def setUp(self):
        d = defer.succeed('value')
        d.addCallback(self._cb_setUpCalled)
        return d

    def _cb_setUpCalled(self, ignored):
        self.fail('deliberate failure')

    def test_ok(self):
        DeferredSetUpCallbackFail.testCalled = True

    
class DeferredSetUpError(unittest.TestCase):
    testCalled = False
    
    def setUp(self):
        return defer.fail(RuntimeError('deliberate error'))

    def test_ok(self):
        DeferredSetUpError.testCalled = True


class DeferredSetUpNeverFire(unittest.TestCase):
    testCalled = False
    
    def setUp(self):
        return defer.Deferred()

    def test_ok(self):
        DeferredSetUpNeverFire.testCalled = True


class DeferredSetUpSkip(unittest.TestCase):
    testCalled = False
    
    def setUp(self):
        d = defer.succeed('value')
        d.addCallback(self._cb1)
        return d

    def _cb1(self, ignored):
        raise unittest.SkipTest("skip me")

    def test_ok(self):
        DeferredSetUpSkip.testCalled = True
