from twisted.python import log
from twisted.internet import utils
from twisted.internet import defer, reactor, threads, interfaces
from twisted.trial import unittest, util
from twisted.trial.test import packages

import sys, os, time

suppress = [(['ignore', 'Do NOT use wait.*'], {})]

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
        self.assertEquals(result, "Beginning")
        d = defer.succeed("End")
        self.assertEquals(util.wait(d), "End")

    def testReturnedDeferredThenWait(self):
        d = self._returnedDeferredThenWait()
        self.assertRaises(util.WaitIsNotReentrantError, util.wait, d)

    def _reentrantWait(self):
        def threadedOperation(n):
            time.sleep(n)
            return n
        d1 = threads.deferToThread(threadedOperation, 0.125)
        d2 = threads.deferToThread(threadedOperation, 0.250)
        d1.addCallback(lambda ignored: util.wait(d2))
        util.wait(d1)

    def testReentrantWait(self):
        self.assertRaises(util.WaitIsNotReentrantError, self._reentrantWait)
        
    def test_twoWaitImplementations(self):
        # If this test times out, then wait is being re-entered.
        tc = TestMktemp('test_name')
        tc._timedOut = False # whitebox
        d = defer.Deferred()
        def _runsInsideWait(r):
            d = defer.Deferred()
            self.assertRaises(util.WaitIsNotReentrantError, util.wait, d)
        d.addCallback(utils.suppressWarnings(_runsInsideWait, *suppress))
        reactor.callLater(0, d.callback, 'yo')
        tc._wait(d)
    test_twoWaitImplementations.timeout = 4


class TestMktemp(unittest.TestCase):
    def test_name(self):
        name = self.mktemp()
        dirs = os.path.dirname(name).split(os.sep)[:-1]
        self.failUnlessEqual(
            dirs, ['twisted.trial.test.test_util', 'TestMktemp', 'test_name'])

    def test_unique(self):
        name = self.mktemp()
        self.failIfEqual(name, self.mktemp())

    def test_created(self):
        name = self.mktemp()
        dirname = os.path.dirname(name)
        self.failUnless(os.path.exists(dirname))
        self.failIf(os.path.exists(name))

    def test_location(self):
        path = os.path.abspath(self.mktemp())
        self.failUnless(path.startswith(os.getcwd()))


class TestWaitInterrupt(unittest.TestCase):

    def raiseKeyInt(self, ignored):
        # XXX Abstraction violation, I suppose.  However: signals are
        # unreliable, so using them to simulate a KeyboardInterrupt
        # would be sketchy too; os.kill() is not available on Windows,
        # so we can't use that and let this run on Win32; raising
        # KeyboardInterrupt itself is wholely unrealistic, as the
        # reactor would normally block SIGINT for its own purposes and
        # not allow a KeyboardInterrupt to happen at all!
        if interfaces.IReactorThreads.providedBy(reactor):
            reactor.callInThread(reactor.sigInt)
        else:
            reactor.callLater(0, reactor.sigInt)
        return defer.Deferred()

    def setUp(self):
        self.shutdownCalled = False

    def testKeyboardInterrupt(self):
        # Test the KeyboardInterrupt is *not* caught by wait -- we
        # want to allow users to Ctrl-C test runs.  And the use of the
        # useWaitError should not matter in this case.
        d = defer.Deferred()
        d.addCallback(self.raiseKeyInt)
        reactor.callLater(0, d.callback, None)
        self.assertRaises(KeyboardInterrupt, util.wait, d, useWaitError=False)

    def _shutdownCalled(self):
        self.shutdownCalled = True

    def test_interruptDoesntShutdown(self):
        reactor.addSystemEventTrigger('after', 'shutdown',
                                      self._shutdownCalled)
        d = defer.Deferred()
        d.addCallback(self.raiseKeyInt)
        reactor.callLater(0, d.callback, None)
        try:
            util.wait(d, useWaitError=False)
        except KeyboardInterrupt:
            self.failIf(self.shutdownCalled,
                        "System shutdown triggered")
        else:
            self.fail("KeyboardInterrupt wasn't raised")

 
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


class TestIntrospection(unittest.TestCase):
    def test_containers(self):
        import suppression
        parents = util.getPythonContainers(
            suppression.TestSuppression2.testSuppressModule)
        expected = [ suppression.TestSuppression2,
                     suppression ]
        for a, b in zip(parents, expected):
            self.failUnlessEqual(a, b)
                     

class TestFindObject(packages.PackageTest):
    def setUp(self):
        packages.PackageTest.setUp(self, '_TestFindObject')
        self.oldPath = sys.path[:]
        sys.path.append('_TestFindObject')

    def tearDown(self):
        sys.path = self.oldPath
        packages.PackageTest.tearDown(self, '_TestFindObject')

    def test_importPackage(self):
        package1 = util.findObject('package')
        import package as package2
        self.failUnlessEqual(package1, (True, package2))

    def test_importModule(self):
        test_sample2 = util.findObject('goodpackage.test_sample')
        from goodpackage import test_sample
        self.failUnlessEqual((True, test_sample), test_sample2)

    def test_importError(self):
        self.failUnlessRaises(ZeroDivisionError,
                              util.findObject, 'package.test_bad_module')

    def test_sophisticatedImportError(self):
        self.failUnlessRaises(ImportError,
                              util.findObject, 'package2.test_module')

    def test_importNonexistentPackage(self):
        self.failUnlessEqual(util.findObject('doesntexist')[0], False)

    def test_findNonexistentModule(self):
        self.failUnlessEqual(util.findObject('package.doesntexist')[0], False)

    def test_findNonexistentObject(self):
        self.failUnlessEqual(util.findObject(
            'goodpackage.test_sample.doesnt')[0], False)
        self.failUnlessEqual(util.findObject(
            'goodpackage.test_sample.AlphabetTest.doesntexist')[0], False)

    def test_findObjectExist(self):
        alpha1 = util.findObject('goodpackage.test_sample.AlphabetTest')
        from goodpackage import test_sample
        self.failUnlessEqual(alpha1, (True, test_sample.AlphabetTest))
        
