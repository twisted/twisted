from twisted.trial import unittest
from twisted.internet import reactor, protocol


"""
in some cases, it is necessary to run trial in a child process to effectively test it's behavior
in erroneous conditions, this module provides such tests
"""

#__tests__ = []

DO_OUTPUT = False

class FoolishError(Exception):
    pass

SET_UP_MSG = "RUNNING SETUP"
SET_UP_CLASS_MSG = "RUNNING SETUPCLASS"
TEAR_DOWN_MSG = "RUNNING TEARDOWN"
TEAR_DOWN_CLASS_MSG = "RUNNING TEARDOWNCLASS"
TESTING_MSG = "I AM A TEST AND I AM RUNNING"

class TestFailureInSetUp(unittest.TestCase):
    def setUp(self):
        if DO_OUTPUT:
            print SET_UP_MSG
        raise FoolishError, "I am a broken setUp method"

    def tearDown(self):
        if DO_OUTPUT:
            print TEAR_DOWN_MSG

    def test_foo(self):
        if DO_OUTPUT:
            print TESTING_MSG


class TestFailureInTearDown(unittest.TestCase):
    def setUp(self):
        if DO_OUTPUT:
            print SET_UP_MSG

    def tearDown(self):
        if DO_OUTPUT:
            print TEAR_DOWN_MSG
        raise FoolishError, "I am a broken tearDown method"

    def test_foo(self):
        if DO_OUTPUT:
            print TESTING_MSG


class TestFailureInSetUpClass(unittest.TestCase):
    def setUpClass(self):
        if DO_OUTPUT:
            print SET_UP_CLASS_MSG
        raise FoolishError, "I am a broken setUpClass method"

    def test_foo(self):
        if DO_OUTPUT:
            print TESTING_MSG
        

class TestFailureInTearDownClass(unittest.TestCase):
    def tearDownClass(self):
        if DO_OUTPUT:
            print TEAR_DOWN_CLASS_MSG
        raise FoolishError, "I am a broken setUp method"

    def test_beforeBrokenTearDownClass(self):
        if DO_OUTPUT:
            print TESTING_MSG


class TestSkipTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_foobar(self):
        if DO_OUTPUT:
            print TESTING_MSG

TestSkipTestCase.skip = "skipping this test"


class TestSkipTestCase2(unittest.TestCase):
    def setUpClass(self):
        raise unittest.SkipTest, "thi stest is fukct"

    def test_thisTestWillBeSkipped(self):
        if DO_OUTPUT:
            print TESTING_MSG

HIDDEN_EXCEPTION_MSG = "something blew up"

class DemoTest(unittest.TestCase):
    def setUp(self):
        self.finished = False

    def go(self):
        if True:
            raise RuntimeError, HIDDEN_EXCEPTION_MSG
        self.finished = True

    def testHiddenException(self):
        import time
        cl = reactor.callLater(0, self.go)
        print "%r" % (cl,)
        timeout = time.time() + 2
        while not (self.finished or time.time() > timeout):
            reactor.iterate(0.1)
        self.failUnless(self.finished)

class ReactorCleanupTests(unittest.TestCase):
    def test_leftoverPendingCalls(self):
        def _():
            print 'foo!'
        reactor.callLater(2, _)

    def test_socketsLeftOpen(self):
        f = protocol.Factory()
        f.protocol = protocol.Protocol
        reactor.listenTCP(0, f)
