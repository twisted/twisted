# -*- test-case-name: twisted.trial.test.test_trial -*-
from twisted.trial import unittest
from twisted.internet import reactor, protocol, defer
from twisted.trial.test.common import BaseTest

"""
in some cases, it is necessary to run trial in a child process to effectively test it's behavior
in erroneous conditions, this module provides such tests
"""

#__tests__ = []

DO_OUTPUT = False

class FoolishError(Exception):
    pass


class TestFailureInSetUp(BaseTest, unittest.TestCase):
    def setUp(self):
        super(TestFailureInSetUp, self).setUp()
        raise FoolishError, "I am a broken setUp method"


class TestFailureInTearDown(BaseTest, unittest.TestCase):
    def tearDown(self):
        super(TestFailureInTearDown, self).tearDown()
        raise FoolishError, "I am a broken tearDown method"


class TestFailureInSetUpClass(BaseTest, unittest.TestCase):
    def setUpClass(self):
        super(TestFailureInSetUpClass, self).setUpClass()
        raise FoolishError, "I am a broken setUpClass method"


class TestFailureInTearDownClass(BaseTest, unittest.TestCase):
    def tearDownClass(self):
        super(TestFailureInTearDownClass, self).tearDownClass()
        raise FoolishError, "I am a broken setUp method"


class TestSkipTestCase(BaseTest, unittest.TestCase):
    pass

TestSkipTestCase.skip = "skipping this test"


class TestSkipTestCase2(BaseTest, unittest.TestCase):
    def setUpClass(self):
        raise unittest.SkipTest, "thi stest is fukct"

    def test_thisTestWillBeSkipped(self):
        self.methodCalled = True
        if DO_OUTPUT:
            print TESTING_MSG

HIDDEN_EXCEPTION_MSG = "something blew up"

class DemoTest(BaseTest, unittest.TestCase):
    def setUp(self):
        super(DemoTest, self).setUp()
        self.finished = False

    def go(self):
        if True:
            raise RuntimeError, HIDDEN_EXCEPTION_MSG
        self.finished = True

    def testHiddenException(self):
        self.methodCalled = True
        import time
        cl = reactor.callLater(0, self.go)
        timeout = time.time() + 2
        while not (self.finished or time.time() > timeout):
            reactor.iterate(0.1)
        self.failUnless(self.finished)

class ReactorCleanupTests(BaseTest, unittest.TestCase):
    def test_leftoverPendingCalls(self):
        self.methodCalled = True
        def _():
            print 'foo!'
        reactor.callLater(10000.0, _)

class SocketOpenTest(BaseTest, unittest.TestCase):
    def test_socketsLeftOpen(self):
        self.methodCalled = True
        f = protocol.Factory()
        f.protocol = protocol.Protocol
        reactor.listenTCP(0, f)

class TimingOutDeferred(BaseTest, unittest.TestCase):
    def test_alpha(self):
        pass

    def test_deferredThatNeverFires(self):
        self.methodCalled = True
        d = defer.Deferred()
        return d

    def test_omega(self):
        pass
