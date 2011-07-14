# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the behaviour of unit tests.
"""

import gc, StringIO, sys, weakref

from twisted.internet import defer, reactor
from twisted.trial import unittest, runner, reporter, util
from twisted.trial.test import erroneous, suppression
from twisted.trial.test.test_reporter import LoggingReporter


class ResultsTestMixin:
    def loadSuite(self, suite):
        self.loader = runner.TestLoader()
        self.suite = self.loader.loadClass(suite)
        self.reporter = reporter.TestResult()

    def test_setUp(self):
        self.failUnless(self.reporter.wasSuccessful())
        self.assertEqual(self.reporter.errors, [])
        self.assertEqual(self.reporter.failures, [])
        self.assertEqual(self.reporter.skips, [])

    def assertCount(self, numTests):
        self.assertEqual(self.suite.countTestCases(), numTests)
        self.suite(self.reporter)
        self.assertEqual(self.reporter.testsRun, numTests)



class TestSuccess(unittest.TestCase):
    """
    Test that successful tests are reported as such.
    """

    def setUp(self):
        self.result = reporter.TestResult()


    def test_successful(self):
        """
        A successful test, used by other tests.
        """


    def assertSuccessful(self, test, result):
        self.assertEqual(result.successes, 1)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.expectedFailures, [])
        self.assertEqual(result.unexpectedSuccesses, [])
        self.assertEqual(result.skips, [])


    def test_successfulIsReported(self):
        """
        Test that when a successful test is run, it is reported as a success,
        and not as any other kind of result.
        """
        test = TestSuccess('test_successful')
        test.run(self.result)
        self.assertSuccessful(test, self.result)


    def test_defaultIsSuccessful(self):
        """
        Test that L{unittest.TestCase} itself can be instantiated, run, and
        reported as being successful.
        """
        test = unittest.TestCase()
        test.run(self.result)
        self.assertSuccessful(test, self.result)


    def test_noReference(self):
        """
        Test that no reference is kept on a successful test.
        """
        test = TestSuccess('test_successful')
        ref = weakref.ref(test)
        test.run(self.result)
        self.assertSuccessful(test, self.result)
        del test
        gc.collect()
        self.assertIdentical(ref(), None)



class TestSkipMethods(unittest.TestCase, ResultsTestMixin):
    class SkippingTests(unittest.TestCase):
        def test_skip1(self):
            raise unittest.SkipTest('skip1')

        def test_skip2(self):
            raise RuntimeError("I should not get raised")
        test_skip2.skip = 'skip2'

        def test_skip3(self):
            self.fail('I should not fail')
        test_skip3.skip = 'skip3'

    class SkippingSetUp(unittest.TestCase):
        def setUp(self):
            raise unittest.SkipTest('skipSetUp')

        def test_1(self):
            pass

        def test_2(self):
            pass

    def setUp(self):
        self.loadSuite(TestSkipMethods.SkippingTests)

    def test_counting(self):
        self.assertCount(3)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.assertEqual(self.reporter.errors, [])
        self.assertEqual(self.reporter.failures, [])
        self.assertEqual(len(self.reporter.skips), 3)

    def test_setUp(self):
        self.loadSuite(TestSkipMethods.SkippingSetUp)
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.assertEqual(self.reporter.errors, [])
        self.assertEqual(self.reporter.failures, [])
        self.assertEqual(len(self.reporter.skips), 2)

    def test_reasons(self):
        self.suite(self.reporter)
        prefix = 'test_'
        # whiteboxing reporter
        for test, reason in self.reporter.skips:
            self.assertEqual(test.shortDescription()[len(prefix):],
                                 str(reason))


class TestSkipClasses(unittest.TestCase, ResultsTestMixin):
    class SkippedClass(unittest.TestCase):
        skip = 'class'
        def setUp(self):
            self.__class__._setUpRan = True
        def test_skip1(self):
            raise unittest.SkipTest('skip1')
        def test_skip2(self):
            raise RuntimeError("Ought to skip me")
        test_skip2.skip = 'skip2'
        def test_skip3(self):
            pass
        def test_skip4(self):
            raise RuntimeError("Skip me too")


    def setUp(self):
        self.loadSuite(TestSkipClasses.SkippedClass)
        TestSkipClasses.SkippedClass._setUpRan = False


    def test_counting(self):
        """
        Skipped test methods still contribute to the total test count.
        """
        self.assertCount(4)


    def test_setUpRan(self):
        """
        The C{setUp} method is not called if the class is set to skip.
        """
        self.suite(self.reporter)
        self.assertFalse(TestSkipClasses.SkippedClass._setUpRan)


    def test_results(self):
        """
        Skipped test methods don't cause C{wasSuccessful} to return C{False},
        nor do they contribute to the C{errors} or C{failures} of the reporter.
        They do, however, add elements to the reporter's C{skips} list.
        """
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.assertEqual(self.reporter.errors, [])
        self.assertEqual(self.reporter.failures, [])
        self.assertEqual(len(self.reporter.skips), 4)


    def test_reasons(self):
        """
        Test methods which raise L{unittest.SkipTest} or have their C{skip}
        attribute set to something are skipped.
        """
        self.suite(self.reporter)
        expectedReasons = ['class', 'skip2', 'class', 'class']
        # whitebox reporter
        reasonsGiven = [reason for test, reason in self.reporter.skips]
        self.assertEqual(expectedReasons, reasonsGiven)



class TestTodo(unittest.TestCase, ResultsTestMixin):
    class TodoTests(unittest.TestCase):
        def test_todo1(self):
            self.fail("deliberate failure")
        test_todo1.todo = "todo1"

        def test_todo2(self):
            raise RuntimeError("deliberate error")
        test_todo2.todo = "todo2"

        def test_todo3(self):
            """unexpected success"""
        test_todo3.todo = 'todo3'

    def setUp(self):
        self.loadSuite(TestTodo.TodoTests)

    def test_counting(self):
        self.assertCount(3)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.assertEqual(self.reporter.errors, [])
        self.assertEqual(self.reporter.failures, [])
        self.assertEqual(self.reporter.skips, [])
        self.assertEqual(len(self.reporter.expectedFailures), 2)
        self.assertEqual(len(self.reporter.unexpectedSuccesses), 1)

    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['todo1', 'todo2']
        reasonsGiven = [ r.reason
                         for t, e, r in self.reporter.expectedFailures ]
        self.assertEqual(expectedReasons, reasonsGiven)

    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = ['todo3']
        reasonsGiven = [ r.reason
                         for t, r in self.reporter.unexpectedSuccesses ]
        self.assertEqual(expectedReasons, reasonsGiven)


class TestTodoClass(unittest.TestCase, ResultsTestMixin):
    class TodoClass(unittest.TestCase):
        def test_todo1(self):
            pass
        test_todo1.todo = "method"
        def test_todo2(self):
            pass
        def test_todo3(self):
            self.fail("Deliberate Failure")
        test_todo3.todo = "method"
        def test_todo4(self):
            self.fail("Deliberate Failure")
    TodoClass.todo = "class"

    def setUp(self):
        self.loadSuite(TestTodoClass.TodoClass)

    def test_counting(self):
        self.assertCount(4)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.assertEqual(self.reporter.errors, [])
        self.assertEqual(self.reporter.failures, [])
        self.assertEqual(self.reporter.skips, [])
        self.assertEqual(len(self.reporter.expectedFailures), 2)
        self.assertEqual(len(self.reporter.unexpectedSuccesses), 2)

    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['method', 'class']
        reasonsGiven = [ r.reason
                         for t, e, r in self.reporter.expectedFailures ]
        self.assertEqual(expectedReasons, reasonsGiven)

    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = ['method', 'class']
        reasonsGiven = [ r.reason
                         for t, r in self.reporter.unexpectedSuccesses ]
        self.assertEqual(expectedReasons, reasonsGiven)


class TestStrictTodo(unittest.TestCase, ResultsTestMixin):
    class Todos(unittest.TestCase):
        def test_todo1(self):
            raise RuntimeError, "expected failure"
        test_todo1.todo = (RuntimeError, "todo1")

        def test_todo2(self):
            raise RuntimeError, "expected failure"
        test_todo2.todo = ((RuntimeError, OSError), "todo2")

        def test_todo3(self):
            raise RuntimeError, "we had no idea!"
        test_todo3.todo = (OSError, "todo3")

        def test_todo4(self):
            raise RuntimeError, "we had no idea!"
        test_todo4.todo = ((OSError, SyntaxError), "todo4")

        def test_todo5(self):
            self.fail("deliberate failure")
        test_todo5.todo = (unittest.FailTest, "todo5")

        def test_todo6(self):
            self.fail("deliberate failure")
        test_todo6.todo = (RuntimeError, "todo6")

        def test_todo7(self):
            pass
        test_todo7.todo = (RuntimeError, "todo7")

    def setUp(self):
        self.loadSuite(TestStrictTodo.Todos)

    def test_counting(self):
        self.assertCount(7)

    def test_results(self):
        self.suite(self.reporter)
        self.failIf(self.reporter.wasSuccessful())
        self.assertEqual(len(self.reporter.errors), 2)
        self.assertEqual(len(self.reporter.failures), 1)
        self.assertEqual(len(self.reporter.expectedFailures), 3)
        self.assertEqual(len(self.reporter.unexpectedSuccesses), 1)
        self.assertEqual(self.reporter.skips, [])

    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['todo1', 'todo2', 'todo5']
        reasonsGotten = [ r.reason
                          for t, e, r in self.reporter.expectedFailures ]
        self.assertEqual(expectedReasons, reasonsGotten)

    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = [([RuntimeError], 'todo7')]
        reasonsGotten = [ (r.errors, r.reason)
                          for t, r in self.reporter.unexpectedSuccesses ]
        self.assertEqual(expectedReasons, reasonsGotten)



class TestCleanup(unittest.TestCase):

    def setUp(self):
        self.result = reporter.Reporter(StringIO.StringIO())
        self.loader = runner.TestLoader()


    def testLeftoverSockets(self):
        """
        Trial reports a L{util.DirtyReactorAggregateError} if a test leaves
        sockets behind.
        """
        suite = self.loader.loadMethod(
            erroneous.SocketOpenTest.test_socketsLeftOpen)
        suite.run(self.result)
        self.failIf(self.result.wasSuccessful())
        # socket cleanup happens at end of class's tests.
        # all the tests in the class are successful, even if the suite
        # fails
        self.assertEqual(self.result.successes, 1)
        failure = self.result.errors[0][1]
        self.failUnless(failure.check(util.DirtyReactorAggregateError))


    def testLeftoverPendingCalls(self):
        """
        Trial reports a L{util.DirtyReactorAggregateError} and fails the test
        if a test leaves a L{DelayedCall} hanging.
        """
        suite = erroneous.ReactorCleanupTests('test_leftoverPendingCalls')
        suite.run(self.result)
        self.failIf(self.result.wasSuccessful())
        failure = self.result.errors[0][1]
        self.assertEqual(self.result.successes, 0)
        self.failUnless(failure.check(util.DirtyReactorAggregateError))



class FixtureTest(unittest.TestCase):
    """
    Tests for broken fixture helper methods (e.g. setUp, tearDown).
    """

    def setUp(self):
        self.reporter = reporter.Reporter()
        self.loader = runner.TestLoader()


    def testBrokenSetUp(self):
        """
        When setUp fails, the error is recorded in the result object.
        """
        self.loader.loadClass(erroneous.TestFailureInSetUp).run(self.reporter)
        self.assert_(len(self.reporter.errors) > 0)
        self.assert_(isinstance(self.reporter.errors[0][1].value,
                                erroneous.FoolishError))


    def testBrokenTearDown(self):
        """
        When tearDown fails, the error is recorded in the result object.
        """
        suite = self.loader.loadClass(erroneous.TestFailureInTearDown)
        suite.run(self.reporter)
        errors = self.reporter.errors
        self.assert_(len(errors) > 0)
        self.assert_(isinstance(errors[0][1].value, erroneous.FoolishError))



class SuppressionTest(unittest.TestCase):

    def runTests(self, suite):
        suite.run(reporter.TestResult())


    def setUp(self):
        self.loader = runner.TestLoader()


    def test_suppressMethod(self):
        """
        A suppression set on a test method prevents warnings emitted by that
        test method which the suppression matches from being emitted.
        """
        self.runTests(self.loader.loadMethod(
            suppression.TestSuppression.testSuppressMethod))
        warningsShown = self.flushWarnings([
                suppression.TestSuppression._emit])
        self.assertEqual(
            warningsShown[0]['message'], suppression.CLASS_WARNING_MSG)
        self.assertEqual(
            warningsShown[1]['message'], suppression.MODULE_WARNING_MSG)
        self.assertEqual(len(warningsShown), 2)


    def test_suppressClass(self):
        """
        A suppression set on a L{TestCase} subclass prevents warnings emitted
        by any test methods defined on that class which match the suppression
        from being emitted.
        """
        self.runTests(self.loader.loadMethod(
            suppression.TestSuppression.testSuppressClass))
        warningsShown = self.flushWarnings([
                suppression.TestSuppression._emit])
        self.assertEqual(
            warningsShown[0]['message'], suppression.METHOD_WARNING_MSG)
        self.assertEqual(
            warningsShown[1]['message'], suppression.MODULE_WARNING_MSG)
        self.assertEqual(len(warningsShown), 2)


    def test_suppressModule(self):
        """
        A suppression set on a module prevents warnings emitted by any test
        mewthods defined in that module which match the suppression from being
        emitted.
        """
        self.runTests(self.loader.loadMethod(
            suppression.TestSuppression2.testSuppressModule))
        warningsShown = self.flushWarnings([
                suppression.TestSuppression._emit])
        self.assertEqual(
            warningsShown[0]['message'], suppression.METHOD_WARNING_MSG)
        self.assertEqual(
            warningsShown[1]['message'], suppression.CLASS_WARNING_MSG)
        self.assertEqual(len(warningsShown), 2)


    def test_overrideSuppressClass(self):
        """
        The suppression set on a test method completely overrides a suppression
        with wider scope; if it does not match a warning emitted by that test
        method, the warning is emitted, even if a wider suppression matches.
        """
        case = self.loader.loadMethod(
            suppression.TestSuppression.testOverrideSuppressClass)
        self.runTests(case)
        warningsShown = self.flushWarnings([
                suppression.TestSuppression._emit])
        self.assertEqual(
            warningsShown[0]['message'], suppression.METHOD_WARNING_MSG)
        self.assertEqual(
            warningsShown[1]['message'], suppression.CLASS_WARNING_MSG)
        self.assertEqual(
            warningsShown[2]['message'], suppression.MODULE_WARNING_MSG)
        self.assertEqual(len(warningsShown), 3)



class GCMixin:
    """
    I provide a few mock tests that log setUp, tearDown, test execution and
    garbage collection. I'm used to test whether gc.collect gets called.
    """

    class BasicTest(unittest.TestCase):
        def setUp(self):
            self._log('setUp')
        def test_foo(self):
            self._log('test')
        def tearDown(self):
            self._log('tearDown')

    class ClassTest(unittest.TestCase):
        def test_1(self):
            self._log('test1')
        def test_2(self):
            self._log('test2')

    def _log(self, msg):
        self._collectCalled.append(msg)

    def collect(self):
        """Fake gc.collect"""
        self._log('collect')

    def setUp(self):
        self._collectCalled = []
        self.BasicTest._log = self.ClassTest._log = self._log
        self._oldCollect = gc.collect
        gc.collect = self.collect

    def tearDown(self):
        gc.collect = self._oldCollect



class TestGarbageCollectionDefault(GCMixin, unittest.TestCase):

    def test_collectNotDefault(self):
        """
        By default, tests should not force garbage collection.
        """
        test = self.BasicTest('test_foo')
        result = reporter.TestResult()
        test.run(result)
        self.assertEqual(self._collectCalled, ['setUp', 'test', 'tearDown'])



class TestGarbageCollection(GCMixin, unittest.TestCase):

    def test_collectCalled(self):
        """
        test gc.collect is called before and after each test.
        """
        test = TestGarbageCollection.BasicTest('test_foo')
        test = unittest._ForceGarbageCollectionDecorator(test)
        result = reporter.TestResult()
        test.run(result)
        self.assertEqual(
            self._collectCalled,
            ['collect', 'setUp', 'test', 'tearDown', 'collect'])



class TestUnhandledDeferred(unittest.TestCase):

    def setUp(self):
        from twisted.trial.test import weird
        # test_unhandledDeferred creates a cycle. we need explicit control of gc
        gc.disable()
        self.test1 = unittest._ForceGarbageCollectionDecorator(
            weird.TestBleeding('test_unhandledDeferred'))

    def test_isReported(self):
        """
        Forcing garbage collection should cause unhandled Deferreds to be
        reported as errors.
        """
        result = reporter.TestResult()
        self.test1(result)
        self.assertEqual(len(result.errors), 1,
                         'Unhandled deferred passed without notice')

    def test_doesntBleed(self):
        """
        Forcing garbage collection in the test should mean that there are
        no unreachable cycles immediately after the test completes.
        """
        result = reporter.TestResult()
        self.test1(result)
        self.flushLoggedErrors() # test1 logs errors that get caught be us.
        # test1 created unreachable cycle.
        # it & all others should have been collected by now.
        n = gc.collect()
        self.assertEqual(n, 0, 'unreachable cycle still existed')
        # check that last gc.collect didn't log more errors
        x = self.flushLoggedErrors()
        self.assertEqual(len(x), 0, 'Errors logged after gc.collect')

    def tearDown(self):
        gc.collect()
        gc.enable()
        self.flushLoggedErrors()



class TestAddCleanup(unittest.TestCase):
    """
    Test the addCleanup method of TestCase.
    """

    class MockTest(unittest.TestCase):

        def setUp(self):
            self.log = ['setUp']

        def brokenSetUp(self):
            self.log = ['setUp']
            raise RuntimeError("Deliberate failure")

        def skippingSetUp(self):
            self.log = ['setUp']
            raise unittest.SkipTest("Don't do this")

        def append(self, thing):
            self.log.append(thing)

        def tearDown(self):
            self.log.append('tearDown')

        def runTest(self):
            self.log.append('runTest')


    def setUp(self):
        unittest.TestCase.setUp(self)
        self.result = reporter.TestResult()
        self.test = TestAddCleanup.MockTest()


    def test_addCleanupCalledIfSetUpFails(self):
        """
        Callables added with C{addCleanup} are run even if setUp fails.
        """
        self.test.setUp = self.test.brokenSetUp
        self.test.addCleanup(self.test.append, 'foo')
        self.test.run(self.result)
        self.assertEqual(['setUp', 'foo'], self.test.log)


    def test_addCleanupCalledIfSetUpSkips(self):
        """
        Callables added with C{addCleanup} are run even if setUp raises
        L{SkipTest}. This allows test authors to reliably provide clean up
        code using C{addCleanup}.
        """
        self.test.setUp = self.test.skippingSetUp
        self.test.addCleanup(self.test.append, 'foo')
        self.test.run(self.result)
        self.assertEqual(['setUp', 'foo'], self.test.log)


    def test_addCleanupCalledInReverseOrder(self):
        """
        Callables added with C{addCleanup} should be called before C{tearDown}
        in reverse order of addition.
        """
        self.test.addCleanup(self.test.append, "foo")
        self.test.addCleanup(self.test.append, 'bar')
        self.test.run(self.result)
        self.assertEqual(['setUp', 'runTest', 'bar', 'foo', 'tearDown'],
                         self.test.log)


    def test_addCleanupWaitsForDeferreds(self):
        """
        If an added callable returns a L{Deferred}, then the test should wait
        until that L{Deferred} has fired before running the next cleanup
        method.
        """
        def cleanup(message):
            d = defer.Deferred()
            reactor.callLater(0, d.callback, message)
            return d.addCallback(self.test.append)
        self.test.addCleanup(self.test.append, 'foo')
        self.test.addCleanup(cleanup, 'bar')
        self.test.run(self.result)
        self.assertEqual(['setUp', 'runTest', 'bar', 'foo', 'tearDown'],
                         self.test.log)


    def test_errorInCleanupIsCaptured(self):
        """
        Errors raised in cleanup functions should be treated like errors in
        C{tearDown}. They should be added as errors and fail the test. Skips,
        todos and failures are all treated as errors.
        """
        self.test.addCleanup(self.test.fail, 'foo')
        self.test.run(self.result)
        self.failIf(self.result.wasSuccessful())
        self.assertEqual(1, len(self.result.errors))
        [(test, error)] = self.result.errors
        self.assertEqual(test, self.test)
        self.assertEqual(error.getErrorMessage(), 'foo')


    def test_cleanupsContinueRunningAfterError(self):
        """
        If a cleanup raises an error then that does not stop the other
        cleanups from being run.
        """
        self.test.addCleanup(self.test.append, 'foo')
        self.test.addCleanup(self.test.fail, 'bar')
        self.test.run(self.result)
        self.assertEqual(['setUp', 'runTest', 'foo', 'tearDown'],
                         self.test.log)
        self.assertEqual(1, len(self.result.errors))
        [(test, error)] = self.result.errors
        self.assertEqual(test, self.test)
        self.assertEqual(error.getErrorMessage(), 'bar')


    def test_multipleErrorsReported(self):
        """
        If more than one cleanup fails, then the test should fail with more
        than one error.
        """
        self.test.addCleanup(self.test.fail, 'foo')
        self.test.addCleanup(self.test.fail, 'bar')
        self.test.run(self.result)
        self.assertEqual(['setUp', 'runTest', 'tearDown'],
                         self.test.log)
        self.assertEqual(2, len(self.result.errors))
        [(test1, error1), (test2, error2)] = self.result.errors
        self.assertEqual(test1, self.test)
        self.assertEqual(test2, self.test)
        self.assertEqual(error1.getErrorMessage(), 'bar')
        self.assertEqual(error2.getErrorMessage(), 'foo')



class TestSuiteClearing(unittest.TestCase):
    """
    Tests for our extension that allows us to clear out a L{TestSuite}.
    """


    def test_clearSuite(self):
        """
        Calling L{unittest._clearSuite} on a populated L{TestSuite} removes
        all tests.
        """
        suite = unittest.TestSuite()
        suite.addTest(unittest.TestCase())
        # Double check that the test suite actually has something in it.
        self.assertEqual(1, suite.countTestCases())
        unittest._clearSuite(suite)
        self.assertEqual(0, suite.countTestCases())


    def test_clearPyunitSuite(self):
        """
        Calling L{unittest._clearSuite} on a populated standard library
        L{TestSuite} removes all tests.

        This test is important since C{_clearSuite} operates by mutating
        internal variables.
        """
        pyunit = __import__('unittest')
        suite = pyunit.TestSuite()
        suite.addTest(unittest.TestCase())
        # Double check that the test suite actually has something in it.
        self.assertEqual(1, suite.countTestCases())
        unittest._clearSuite(suite)
        self.assertEqual(0, suite.countTestCases())



class TestTestDecorator(unittest.TestCase):
    """
    Tests for our test decoration features.
    """


    def assertTestsEqual(self, observed, expected):
        """
        Assert that the given decorated tests are equal.
        """
        self.assertEqual(observed.__class__, expected.__class__,
                         "Different class")
        observedOriginal = getattr(observed, '_originalTest', None)
        expectedOriginal = getattr(expected, '_originalTest', None)
        self.assertIdentical(observedOriginal, expectedOriginal)
        if observedOriginal is expectedOriginal is None:
            self.assertIdentical(observed, expected)


    def assertSuitesEqual(self, observed, expected):
        """
        Assert that the given test suites with decorated tests are equal.
        """
        self.assertEqual(observed.__class__, expected.__class__,
                         "Different class")
        self.assertEqual(len(observed._tests), len(expected._tests),
                         "Different number of tests.")
        for observedTest, expectedTest in zip(observed._tests,
                                              expected._tests):
            if getattr(observedTest, '_tests', None) is not None:
                self.assertSuitesEqual(observedTest, expectedTest)
            else:
                self.assertTestsEqual(observedTest, expectedTest)


    def test_usesAdaptedReporterWithRun(self):
        """
        For decorated tests, C{run} uses a result adapter that preserves the
        test decoration for calls to C{addError}, C{startTest} and the like.

        See L{reporter._AdaptedReporter}.
        """
        test = unittest.TestCase()
        decoratedTest = unittest.TestDecorator(test)
        result = LoggingReporter()
        decoratedTest.run(result)
        self.assertTestsEqual(result.test, decoratedTest)


    def test_usesAdaptedReporterWithCall(self):
        """
        For decorated tests, C{__call__} uses a result adapter that preserves
        the test decoration for calls to C{addError}, C{startTest} and the
        like.

        See L{reporter._AdaptedReporter}.
        """
        test = unittest.TestCase()
        decoratedTest = unittest.TestDecorator(test)
        result = LoggingReporter()
        decoratedTest(result)
        self.assertTestsEqual(result.test, decoratedTest)


    def test_decorateSingleTest(self):
        """
        Calling L{decorate} on a single test case returns the test case
        decorated with the provided decorator.
        """
        test = unittest.TestCase()
        decoratedTest = unittest.decorate(test, unittest.TestDecorator)
        self.assertTestsEqual(unittest.TestDecorator(test), decoratedTest)


    def test_decorateTestSuite(self):
        """
        Calling L{decorate} on a test suite will return a test suite with
        each test decorated with the provided decorator.
        """
        test = unittest.TestCase()
        suite = unittest.TestSuite([test])
        decoratedTest = unittest.decorate(suite, unittest.TestDecorator)
        self.assertSuitesEqual(
            decoratedTest, unittest.TestSuite([unittest.TestDecorator(test)]))


    def test_decorateInPlaceMutatesOriginal(self):
        """
        Calling L{decorate} on a test suite will mutate the original suite.
        """
        test = unittest.TestCase()
        suite = unittest.TestSuite([test])
        decoratedTest = unittest.decorate(
            suite, unittest.TestDecorator)
        self.assertSuitesEqual(
            decoratedTest, unittest.TestSuite([unittest.TestDecorator(test)]))
        self.assertSuitesEqual(
            suite, unittest.TestSuite([unittest.TestDecorator(test)]))


    def test_decorateTestSuiteReferences(self):
        """
        When decorating a test suite in-place, the number of references to the
        test objects in that test suite should stay the same.

        Previously, L{unittest.decorate} recreated a test suite, so the
        original suite kept references to the test objects. This test is here
        to ensure the problem doesn't reappear again.
        """
        getrefcount = getattr(sys, 'getrefcount', None)
        if getrefcount is None:
            raise unittest.SkipTest(
                "getrefcount not supported on this platform")
        test = unittest.TestCase()
        suite = unittest.TestSuite([test])
        count1 = getrefcount(test)
        decoratedTest = unittest.decorate(suite, unittest.TestDecorator)
        count2 = getrefcount(test)
        self.assertEqual(count1, count2)


    def test_decorateNestedTestSuite(self):
        """
        Calling L{decorate} on a test suite with nested suites will return a
        test suite that maintains the same structure, but with all tests
        decorated.
        """
        test = unittest.TestCase()
        suite = unittest.TestSuite([unittest.TestSuite([test])])
        decoratedTest = unittest.decorate(suite, unittest.TestDecorator)
        expected = unittest.TestSuite(
            [unittest.TestSuite([unittest.TestDecorator(test)])])
        self.assertSuitesEqual(decoratedTest, expected)


    def test_decorateDecoratedSuite(self):
        """
        Calling L{decorate} on a test suite with already-decorated tests
        decorates all of the tests in the suite again.
        """
        test = unittest.TestCase()
        decoratedTest = unittest.decorate(test, unittest.TestDecorator)
        redecoratedTest = unittest.decorate(decoratedTest,
                                            unittest.TestDecorator)
        self.assertTestsEqual(redecoratedTest,
                              unittest.TestDecorator(decoratedTest))


    def test_decoratePreservesSuite(self):
        """
        Tests can be in non-standard suites. L{decorate} preserves the
        non-standard suites when it decorates the tests.
        """
        test = unittest.TestCase()
        suite = runner.DestructiveTestSuite([test])
        decorated = unittest.decorate(suite, unittest.TestDecorator)
        self.assertSuitesEqual(
            decorated,
            runner.DestructiveTestSuite([unittest.TestDecorator(test)]))


class TestMonkeyPatchSupport(unittest.TestCase):
    """
    Tests for the patch() helper method in L{unittest.TestCase}.
    """


    def setUp(self):
        self.originalValue = 'original'
        self.patchedValue = 'patched'
        self.objectToPatch = self.originalValue
        self.test = unittest.TestCase()


    def test_patch(self):
        """
        Calling C{patch()} on a test monkey patches the specified object and
        attribute.
        """
        self.test.patch(self, 'objectToPatch', self.patchedValue)
        self.assertEqual(self.objectToPatch, self.patchedValue)


    def test_patchRestoredAfterRun(self):
        """
        Any monkey patches introduced by a test using C{patch()} are reverted
        after the test has run.
        """
        self.test.patch(self, 'objectToPatch', self.patchedValue)
        self.test.run(reporter.Reporter())
        self.assertEqual(self.objectToPatch, self.originalValue)


    def test_revertDuringTest(self):
        """
        C{patch()} return a L{monkey.MonkeyPatcher} object that can be used to
        restore the original values before the end of the test.
        """
        patch = self.test.patch(self, 'objectToPatch', self.patchedValue)
        patch.restore()
        self.assertEqual(self.objectToPatch, self.originalValue)


    def test_revertAndRepatch(self):
        """
        The returned L{monkey.MonkeyPatcher} object can re-apply the patch
        during the test run.
        """
        patch = self.test.patch(self, 'objectToPatch', self.patchedValue)
        patch.restore()
        patch.patch()
        self.assertEqual(self.objectToPatch, self.patchedValue)


    def test_successivePatches(self):
        """
        Successive patches are applied and reverted just like a single patch.
        """
        self.test.patch(self, 'objectToPatch', self.patchedValue)
        self.assertEqual(self.objectToPatch, self.patchedValue)
        self.test.patch(self, 'objectToPatch', 'second value')
        self.assertEqual(self.objectToPatch, 'second value')
        self.test.run(reporter.Reporter())
        self.assertEqual(self.objectToPatch, self.originalValue)



class TestIterateTests(unittest.TestCase):
    """
    L{_iterateTests} returns a list of all test cases in a test suite or test
    case.
    """

    def test_iterateTestCase(self):
        """
        L{_iterateTests} on a single test case returns a list containing that
        test case.
        """
        test = unittest.TestCase()
        self.assertEqual([test], list(unittest._iterateTests(test)))


    def test_iterateSingletonTestSuite(self):
        """
        L{_iterateTests} on a test suite that contains a single test case
        returns a list containing that test case.
        """
        test = unittest.TestCase()
        suite = runner.TestSuite([test])
        self.assertEqual([test], list(unittest._iterateTests(suite)))


    def test_iterateNestedTestSuite(self):
        """
        L{_iterateTests} returns tests that are in nested test suites.
        """
        test = unittest.TestCase()
        suite = runner.TestSuite([runner.TestSuite([test])])
        self.assertEqual([test], list(unittest._iterateTests(suite)))


    def test_iterateIsLeftToRightDepthFirst(self):
        """
        L{_iterateTests} returns tests in left-to-right, depth-first order.
        """
        test = unittest.TestCase()
        suite = runner.TestSuite([runner.TestSuite([test]), self])
        self.assertEqual([test, self], list(unittest._iterateTests(suite)))
