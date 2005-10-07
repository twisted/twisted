import cPickle as pickle
import warnings
import StringIO

from twisted.trial.reporter import SKIP, EXPECTED_FAILURE, FAILURE, ERROR, UNEXPECTED_SUCCESS, SUCCESS
from twisted.trial import unittest, runner, reporter, util, itrial
from twisted.python import log, failure, reflect
from twisted.python.util import dsu
from twisted.python.compat import adict
from twisted.internet import defer, reactor


TIMEOUT_MSG = "this is a timeout arg"
CLASS_TIMEOUT_MSG = "this is a class level timeout arg"


class MockEquality(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "MockEquality(%s)" % (self.name,)

    def __eq__(self, other):
        if not hasattr(other, 'name'):
            raise ValueError("%r not comparable to %r" % (other, self))
        return self.name[0] == other.name[0]


class TestAssertions(unittest.TestCase):
    """Tests for TestCase's assertion methods.  That is, failUnless*,
    failIf*, assert*.

    This is pretty paranoid.  Still, a certain paranoia is healthy if you
    are testing a unit testing framework.
    """
    
    class FailingTest(unittest.TestCase):
        def test_fails(self):
            raise TestAssertions.failureException()

    def testFail(self):
        try:
            self.fail("failed")
        except self.failureException, e:
            if not str(e) == 'failed':
                raise self.failureException("Exception had msg %s instead of %s"
                                            % str(e), 'failed')
        else:
            raise self.failureException("Call to self.fail() didn't fail test")

    def test_failingException_fails(self):
        test = runner.TestLoader().loadClass(TestAssertions.FailingTest)
        io = StringIO.StringIO()
        result = reporter.Reporter(stream=io)
        test.run(result)
        self.failIf(result.wasSuccessful())
        self.failUnlessEqual(len(result.errors), 0)
        self.failUnlessEqual(len(result.failures), 1)

    def test_failIf(self):
        for notTrue in [0, 0.0, False, None, (), []]:
            self.failIf(notTrue, "failed on %r" % (notTrue,))
        for true in [1, True, 'cat', [1,2], (3,4)]:
            try:
                self.failIf(true, "failed on %r" % (true,))
            except self.failureException, e:
                self.failUnlessEqual(str(e), "failed on %r" % (true,))
            else:
                self.fail("Call to failIf(%r) didn't fail" % (true,))

    def test_failUnless(self):
        for notTrue in [0, 0.0, False, None, (), []]:
            try:
                self.failUnless(notTrue, "failed on %r" % (notTrue,))
            except self.failureException, e:
                self.failUnlessEqual(str(e), "failed on %r" % (notTrue,))
            else:
                self.fail("Call to failUnless(%r) didn't fail" % (notTrue,))
        for true in [1, True, 'cat', [1,2], (3,4)]:
            self.failUnless(true, "failed on %r" % (true,))

    def _testEqualPair(self, first, second):
        x = self.failUnlessEqual(first, second)
        if x != first:
            self.fail("failUnlessEqual should return first parameter")

    def _testUnequalPair(self, first, second):
        try:
            self.failUnlessEqual(first, second)
        except self.failureException, e:
            expected = '%r != %r' % (first, second)
            if str(e) != expected:
                self.fail("Expected: %r; Got: %s" % (expected, str(e)))
        else:
            self.fail("Call to failUnlessEqual(%r, %r) didn't fail"
                      % (first, second))

    def test_failUnlessEqual_basic(self):
        self._testEqualPair('cat', 'cat')
        self._testUnequalPair('cat', 'dog')
        self._testEqualPair([1], [1])
        self._testUnequalPair([1], 'orange')
    
    def test_failUnlessEqual_custom(self):
        x = MockEquality('first')
        y = MockEquality('second')
        z = MockEquality('fecund')
        self._testEqualPair(x, x)
        self._testEqualPair(x, z)
        self._testUnequalPair(x, y)
        self._testUnequalPair(y, z)

    def test_failUnlessEqual_incomparable(self):
        apple = MockEquality('apple')
        orange = ['orange']
        try:
            self.failUnlessEqual(apple, orange)
        except self.failureException:
            self.fail("Fail raised when ValueError ought to have been raised.")
        except ValueError:
            # good. error not swallowed
            pass
        else:
            self.fail("Comparing %r and %r should have raised an exception"
                      % (apple, orange))

    def _raiseError(self, error):
        raise error

    def test_failUnlessRaises_expected(self):
        x = self.failUnlessRaises(ValueError, self._raiseError, ValueError)
        self.failUnless(isinstance(x, ValueError),
                        "Expect failUnlessRaises to return instance of raised "
                        "exception.")

    def test_failUnlessRaises_unexpected(self):
        try:
            self.failUnlessRaises(ValueError, self._raiseError, TypeError)
        except TypeError:
            self.fail("failUnlessRaises shouldn't re-raise unexpected "
                      "exceptions")
        except self.failureException, e:
            # what we expect
            pass
        else:
            self.fail("Expected exception wasn't raised. Should have failed")

    def test_failUnlessRaises_noException(self):
        try:
            self.failUnlessRaises(ValueError, lambda : None)
        except self.failureException, e:
            self.failUnlessEqual(str(e),
                                 'ValueError not raised (None returned)')
        else:
            self.fail("Exception not raised. Should have failed")

    def test_failUnlessRaises_failureException(self):
        x = self.failUnlessRaises(self.failureException, self._raiseError,
                                  self.failureException)
        self.failUnless(isinstance(x, self.failureException),
                        "Expected %r instance to be returned"
                        % (self.failureException,))
        try:
            x = self.failUnlessRaises(self.failureException, self._raiseError,
                                      ValueError)
        except self.failureException, e:
            # what we expect
            pass
        else:
            self.fail("Should have raised exception")

    def test_failIfEqual_basic(self):
        x, y, z = [1], [2], [1]
        ret = self.failIfEqual(x, y)
        self.failUnlessEqual(ret, x,
                             "failIfEqual should return first parameter")
        self.failUnlessRaises(self.failureException,
                              self.failIfEqual, x, x)
        self.failUnlessRaises(self.failureException,
                              self.failIfEqual, x, z)

    def test_failIfEqual_customEq(self):
        x = MockEquality('first')
        y = MockEquality('second')
        z = MockEquality('fecund')
        ret = self.failIfEqual(x, y)
        self.failUnlessEqual(ret, x,
                             "failIfEqual should return first parameter")
        self.failUnlessRaises(self.failureException,
                              self.failIfEqual, x, x)
        # test when __ne__ is not defined
        self.failIfEqual(x, z, "__ne__ not defined, so not equal")

    def test_failUnlessIdentical(self):
        x, y, z = [1], [1], [2]
        ret = self.failUnlessIdentical(x, x)
        self.failUnlessEqual(ret, x,
                             'failUnlessIdentical should return first '
                             'parameter')
        self.failUnlessRaises(self.failureException,
                              self.failUnlessIdentical, x, y)
        self.failUnlessRaises(self.failureException,
                              self.failUnlessIdentical, x, z)

    def test_failUnlessApproximates(self):
        x, y, z = 1.0, 1.1, 1.2
        self.failUnlessApproximates(x, x, 0.2)
        ret = self.failUnlessApproximates(x, y, 0.2)
        self.failUnlessEqual(ret, x, "failUnlessApproximates should return "
                             "first parameter")
        self.failUnlessRaises(self.failureException,
                              self.failUnlessApproximates, x, z, 0.1)
        self.failUnlessRaises(self.failureException,
                              self.failUnlessApproximates, x, y, 0.1)

    def test_failUnlessAlmostEqual(self):
        precision = 5
        x = 8.000001
        y = 8.00001
        z = 8.000002
        self.failUnlessAlmostEqual(x, x, precision)
        ret = self.failUnlessAlmostEqual(x, z, precision)
        self.failUnlessEqual(ret, x, "failUnlessAlmostEqual should return "
                             "first parameter (%r, %r)" % (ret, x))
        self.failUnlessRaises(self.failureException,
                              self.failUnlessAlmostEqual, x, y, precision)
        
    def test_failIfAlmostEqual(self):
        precision = 5
        x = 8.000001
        y = 8.00001
        z = 8.000002
        ret = self.failIfAlmostEqual(x, y, precision)
        self.failUnlessEqual(ret, x, "failIfAlmostEqual should return "
                             "first parameter (%r, %r)" % (ret, x))
        self.failUnlessRaises(self.failureException,
                              self.failIfAlmostEqual, x, x, precision)
        self.failUnlessRaises(self.failureException,
                              self.failIfAlmostEqual, x, z, precision)

    def test_failUnlessSubstring(self):
        x = "cat"
        y = "the dog sat"
        z = "the cat sat"
        self.failUnlessSubstring(x, x)
        ret = self.failUnlessSubstring(x, z)
        self.failUnlessEqual(ret, x, 'should return first parameter')
        self.failUnlessRaises(self.failureException,
                              self.failUnlessSubstring, x, y)
        self.failUnlessRaises(self.failureException,
                              self.failUnlessSubstring, z, x)

    def test_failIfSubstring(self):
        x = "cat"
        y = "the dog sat"
        z = "the cat sat"
        self.failIfSubstring(z, x)
        ret = self.failIfSubstring(x, y)
        self.failUnlessEqual(ret, x, 'should return first parameter')
        self.failUnlessRaises(self.failureException,
                              self.failIfSubstring, x, x)
        self.failUnlessRaises(self.failureException,
                              self.failIfSubstring, x, z)


class TestAssertionNames(unittest.TestCase):
    """Tests for consistency of naming within TestCase assertion methods
    """
    def _getAsserts(self):
        dct = {}
        reflect.accumulateMethods(self, dct, 'assert')
        return [ dct[k] for k in dct if not k.startswith('Not') and k != '_' ]

    def _name(self, x):
        return x.__name__

    def test_failUnless_matches_assert(self):
        asserts = self._getAsserts()
        failUnlesses = reflect.prefixedMethods(self, 'failUnless')
        self.failUnlessEqual(dsu(asserts, self._name),
                             dsu(failUnlesses, self._name))

    def test_failIf_matches_assertNot(self):
        asserts = reflect.prefixedMethods(unittest.TestCase, 'assertNot')
        failIfs = reflect.prefixedMethods(unittest.TestCase, 'failIf')
        self.failUnlessEqual(dsu(asserts, self._name),
                             dsu(failIfs, self._name))

    def test_equalSpelling(self):
        for name, value in vars(self).items():
            if not callable(value):
                continue
            if name.endswith('Equal'):
                self.failUnless(hasattr(self, name+'s'),
                                "%s but no %ss" % (name, name))
                self.failUnlessEqual(value, getattr(self, name+'s'))
            if name.endswith('Equals'):
                self.failUnless(hasattr(self, name[:-1]),
                                "%s but no %s" % (name, name[:-1]))
                self.failUnlessEqual(value, getattr(self, name[:-1]))


class ResultsTestMixin:
    def loadSuite(self, suite):
        self.loader = runner.TestLoader()
        self.suite = self.loader.loadClass(suite)
        self.reporter = reporter.Reporter(stream=StringIO.StringIO())

    def test_setUp(self):
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(self.reporter.skips, [])
        
    def assertCount(self, numTests):
        self.failUnlessEqual(self.suite.countTestCases(), numTests)
        self.suite(self.reporter)
        self.failUnlessEqual(self.reporter.testsRun, numTests)


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

    def setUp(self):
        self.loadSuite(TestSkipMethods.SkippingTests)

    def test_counting(self):
        self.assertCount(3)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(len(self.reporter.skips), 3)

    def test_reasons(self):
        self.suite(self.reporter)
        prefix = 'test_'
        # whiteboxing reporter 
        for test, reason in self.reporter.skips:
            self.failUnlessEqual(test.shortDescription()[len(prefix):],
                                 str(reason))


class TestSkipClasses(unittest.TestCase, ResultsTestMixin):
    class SkippedClass(unittest.TestCase):
        skip = 'class'
        def test_skip1(self):
            raise SkipTest('skip1')
        def test_skip2(self):
            raise RuntimeError("Ought to skip me")
        test_skip2.skip = 'skip2'
        def test_skip3(self):
            pass
        def test_skip4(self):
            raise RuntimeError("Skip me too")
        
    def setUp(self):
        self.loadSuite(TestSkipClasses.SkippedClass)

    def test_counting(self):
        self.assertCount(4)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(len(self.reporter.skips), 4)

    def test_reasons(self):
        self.suite(self.reporter)
        expectedReasons = ['class', 'skip2', 'class', 'class']
        # whitebox reporter
        reasonsGiven = [ reason for test, reason in self.reporter.skips ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)


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
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(self.reporter.skips, [])
        self.failUnlessEqual(len(self.reporter.expectedFailures), 2)
        self.failUnlessEqual(len(self.reporter.unexpectedSuccesses), 1)
    
    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['todo1', 'todo2']
        reasonsGiven = [ r for t, e, r in self.reporter.expectedFailures ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)
            
    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = ['todo3']
        reasonsGiven = [ r for t, r in self.reporter.unexpectedSuccesses ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)


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
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(self.reporter.skips, [])
        self.failUnlessEqual(len(self.reporter.expectedFailures), 2)
        self.failUnlessEqual(len(self.reporter.unexpectedSuccesses), 2)
    
    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['method', 'class']
        reasonsGiven = [ r for t, e, r in self.reporter.expectedFailures ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)
            
    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = ['method', 'class']
        reasonsGiven = [ r for t, r in self.reporter.unexpectedSuccesses ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)


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
        self.failUnlessEqual(len(self.reporter.errors), 2)
        self.failUnlessEqual(len(self.reporter.failures), 1)
        self.failUnlessEqual(len(self.reporter.expectedFailures), 3)
        self.failUnlessEqual(len(self.reporter.unexpectedSuccesses), 1)
        self.failUnlessEqual(self.reporter.skips, [])

    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['todo1', 'todo2', 'todo5']
        reasonsGotten = [ r for t, e, r in self.reporter.expectedFailures ]
        self.failUnlessEqual(expectedReasons, reasonsGotten)

    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = [(RuntimeError, 'todo7')]
        reasonsGotten = [ r for t, r in self.reporter.unexpectedSuccesses ]
        self.failUnlessEqual(expectedReasons, reasonsGotten)

    
class TestTests(unittest.TestCase):
    # first, the things we're going to test
    class Tests(unittest.TestCase):
        def testDeferred1_pass(self):
            return defer.succeed('hoorj!')
        def testDeferred2_fail(self):
            return defer.fail(unittest.FailTest('i fail'))
        def testDeferred3_fail(self):
            return self.fail('this test fails')
        def testDeferred4_error(self):
            return defer.fail(RuntimeError('suck it'))
        def testDeferred5_skip(self):
            return defer.fail(unittest.SkipTest('lalala, skip me'))
        def testDeferred7_exfail(self):
            return defer.fail(unittest.FailTest('you got an F!'))
        testDeferred7_exfail.todo = "i'm gonna get an F"
        def testDeferred8_exfail(self):
            return defer.fail(RuntimeError('you got another F!'))
        testDeferred8_exfail.todo = "I'm gonna get another F"
        
        def testTimeout1_pass(self):
            d = defer.Deferred()
            reactor.callLater(0, d.callback, 'hoorj!')
            return d
        testTimeout1_pass.timeout = 2
        def testTimeout2_pass(self):
            # test default timeout time of 4
            d = defer.Deferred()
            reactor.callLater(0, d.callback, 'hoorj!')
            return d
        def testTimeout3_error(self):
            return defer.Deferred()
        testTimeout3_error.timeout = 0
        def testTimeout4_exfail(self):
            return defer.Deferred()
        testTimeout4_exfail.timeout = 0
        testTimeout4_exfail.todo = "i will get it right, eventually"
        def testTimeout5_skip(self):
            return defer.Deferred()
        testTimeout5_skip.timeout = 0.1
        testTimeout5_skip.skip = "i will get it right, eventually"

    def checkResults(self, reporter, method):
        tm = method
        self.failUnlessEqual(tm.countTestCases(), 1)
        self.failUnless(tm.startTime >= 0)

        def _hasTbs(meth):
            return not (len(reporter._getFailures(meth))
                        == len(reporter._getErrors(meth))
                        == len(reporter._getExpectedFailures(meth))
                        == 0)

        def _checkStatus(meth, status):
            statusmsg = ("test did not return status %s, instead returned %s"
                         % (status, reporter.getStatus(meth)))
            if reporter._getErrors(meth) and status is not ERROR:
                tb = ''.join([f.getTraceback()
                              for f in reporter._getErrors(meth)])
                tb = ''.join(["\t%s\n" % line for line in tb.split('\n')])
                statusmsg += "\n\n%s" % (tb)
            self.failUnlessEqual(reporter.getStatus(meth), status, statusmsg)

        def _checkTimeoutError(meth):
            if meth.getTimeout() is not None:
                self.failUnless(_hasTbs(meth), 'method did not have tracebacks!')
                errors = (reporter._getErrors(meth)
                          or reporter._getExpectedFailures(meth))
                f = errors[0]
                self.failUnlessEqual(f.type, defer.TimeoutError)

        try:
            self.failUnless(tm.startTime >= 0.0, "%f not >= 0.0" % (tm.startTime,))

            if tm.id().endswith("_pass"):
                _checkStatus(tm, SUCCESS)
                self.failIf(tm.getTodo())
                self.failIf(_hasTbs(tm))
                self.failIf(tm.getSkip())

            elif tm.id().endswith("_fail"):
                _checkStatus(tm, FAILURE)
                _checkTimeoutError(tm)
                self.failIf(tm.getSkip())
                self.failIf(reporter._getErrors(tm))
                self.failUnless(_hasTbs(tm))
                self.failUnless(len(reporter._getFailures(tm)) == 1,
                                "%s had %d failures"
                                % (tm.id(), len(reporter._getFailures(tm))))
            elif tm.id().endswith("_error"):
                _checkStatus(tm, ERROR)
                _checkTimeoutError(tm)
                self.failUnless(_hasTbs(tm))
                self.failUnless(len(reporter._getErrors(tm)) == 1,
                                "%s had %d errors" % (tm.id(),
                                                      len(reporter._getErrors(tm))))

                # with new-style todos it's possible for a todoed method to
                # wind up counting as a ERROR
                # failIf(tm.todo)
                self.failIf(tm.getSkip())
                self.failIf(reporter._getFailures(tm))

            elif tm.id().endswith("_skip"):
                _checkStatus(tm, SKIP)
                self.failUnless(tm.getSkip(), "skip reason not set")
                self.failIf(tm.getTodo())
                self.failIf(reporter._getErrors(tm))
                self.failIf(reporter._getFailures(tm))
                self.failIf(_hasTbs(tm))

            elif tm.id().endswith("_exfail"):
                _checkStatus(tm, EXPECTED_FAILURE)
                _checkTimeoutError(tm)
                self.failUnless(_hasTbs(tm))
                self.failUnless(tm.getTodo())
                self.failIf(tm.getSkip())

            elif tm.id().endswith("_unexpass"):
                _checkStatus(tm, UNEXPECTED_SUCCESS)
                _checkTimeoutError(tm)
                self.failUnless(tm.getTodo())
                self.failIf(tm.getSkip())

            elif tm.id().endswith("_timeout"):
                self.failUnless(reporter._getErrors(tm), "tm.errors was %s" % (reporter._getErrors(tm),))
                expectedExc, f = tm.original.t_excClass, reporter._getErrors(tm)[0]
                self.failUnless(f.check(expectedExc),
                                "exception '%s', with tb:\n%s\n\n was not of expected type '%s'"
                                % (f, f.getTraceback(), expectedExc))
                self.failUnlessEqual(f.value.args[0], tm.original.t_excArg)
                self.failUnlessEqual(itrial.ITimeout(tm.getTimeout()).duration, tm.original.t_duration)

            elif tm.id().endswith("_timeoutClassAttr"):
                self.failUnless(reporter._getErrors(tm), "tm.errors was %s" % (reporter._getErrors(tm),))
                expectedExc, f = tm.klass.t_excClass, reporter._getErrors(tm)[0]
                self.failUnless(f.check(expectedExc),
                                "exception '%s', with tb:\n%s\n\n was not of expected type '%s'"
                                % (f, f.getTraceback(), expectedExc))
                self.failUnlessEqual(f.value.args[0], tm.klass.t_excArg)
                self.failUnlessEqual(itrial.ITimeout(tm.getTimeout()).duration, tm.klass.t_duration)
            else:
                raise unittest.FailTest, "didn't have tests for a method ending in %s" % (
                                         tm.id().split('_')[-1],)
        except unittest.FailTest:
            tb = failure.Failure().getTraceback()
            raise unittest.FailTest, "error occured in test %s: %s" % (tm.id(), tb)
        

    def testMethods(self):
        from twisted.trial.test.common import BogusReporter
        reporter = BogusReporter()
        suite = runner.TestLoader().loadClass(self.Tests)
        root = runner.TrialRoot(reporter)
        root.run(suite)
        for method in suite._tests:
            try:
                self.checkResults(reporter, method)
            except unittest.FailTest:
                raise



