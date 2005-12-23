# -*- test-case-name: twisted.trial.test.test_tests -*-
from twisted.trial import unittest
from twisted.internet import reactor, protocol, defer


class FoolishError(Exception):
    pass


class TestFailureInSetUp(unittest.TestCase):
    def setUp(self):
        raise FoolishError, "I am a broken setUp method"

    def test_noop(self):
        pass


class TestFailureInTearDown(unittest.TestCase):
    def tearDown(self):
        raise FoolishError, "I am a broken tearDown method"

    def test_noop(self):
        pass


class TestFailureInSetUpClass(unittest.TestCase):
    def setUpClass(self):
        raise FoolishError, "I am a broken setUpClass method"

    def test_noop(self):
        pass


class TestFailureInTearDownClass(unittest.TestCase):
    def tearDownClass(self):
        raise FoolishError, "I am a broken setUp method"

    def test_noop(self):
        pass


class TestRegularFail(unittest.TestCase):
    def test_fail(self):
        self.fail("I fail")


class TestSkipTestCase(unittest.TestCase):
    pass

TestSkipTestCase.skip = "skipping this test"


class TestSkipTestCase2(unittest.TestCase):
    
    def setUpClass(self):
        raise unittest.SkipTest, "thi stest is fukct"

    def test_thisTestWillBeSkipped(self):
        pass

HIDDEN_EXCEPTION_MSG = "something blew up"

class DemoTest(unittest.TestCase):
    def setUp(self):
        super(DemoTest, self).setUp()
        self.finished = False

    def go(self):
        if True:
            raise RuntimeError, HIDDEN_EXCEPTION_MSG
        self.finished = True

    def testHiddenException(self):
        import time
        cl = reactor.callLater(0, self.go)
        timeout = time.time() + 2
        while not (self.finished or time.time() > timeout):
            reactor.iterate(0.1)
        self.failUnless(self.finished)

class ReactorCleanupTests(unittest.TestCase):
    def test_leftoverPendingCalls(self):
        def _():
            print 'foo!'
        reactor.callLater(10000.0, _)

class SocketOpenTest(unittest.TestCase):
    def test_socketsLeftOpen(self):
        f = protocol.Factory()
        f.protocol = protocol.Protocol
        reactor.listenTCP(0, f)

class TimingOutDeferred(unittest.TestCase):
    def test_alpha(self):
        pass

    def test_deferredThatNeverFires(self):
        self.methodCalled = True
        d = defer.Deferred()
        return d

    def test_omega(self):
        pass


def unexpectedException(self):
    """i will raise an unexpected exception...
    ... *CAUSE THAT'S THE KINDA GUY I AM*
    
    >>> 1/0
    """

