import cPickle as pickle
import warnings

from twisted.trial.reporter import SKIP, EXPECTED_FAILURE, FAILURE, ERROR, UNEXPECTED_SUCCESS, SUCCESS
from twisted.trial import unittest, runner, reporter, util, itrial, adapters
from twisted.trial.unittest import failUnless, failUnlessRaises, failIf, failUnlessEqual
from twisted.trial.unittest import failUnlessSubstring, failIfSubstring
from twisted.python import log, failure
from twisted.python.compat import adict
from twisted.internet import defer, reactor


TIMEOUT_MSG = "this is a timeout arg"
CLASS_TIMEOUT_MSG = "this is a class level timeout arg"

METHOD_SKIP_MSG = "skip this method"
CLASS_SKIP_MSG = "skip all methods in this class"

METHOD_TODO_MSG = "todo this method"
CLASS_TODO_MSG = "todo all methods in this class"

class TestTests(unittest.TestCase):
    # first, the things we're going to test
    class Tests(unittest.TestCase):
        def __init__(self):
            self.setupRun = 0
            self.teardownRun = 0
        def setUp(self):
            self.setupRun += 1
        def tearDown(self):
            self.teardownRun += 1
        def testSuccess_pass(self):
            pass
        def testFail_fail(self):
            self.fail("failed")
        def testFailIf_pass(self):
            self.failIf(0, "failed")
        def testFailIf_fail(self):
            self.failIf(1, "failed")
        def testFailUnless_pass(self):
            self.failUnless(1, "failed")
        def testFailUnless_fail(self):
            self.failUnless(0, "failed")
        def testFailUnlessRaises_pass(self):
            def boom():
                raise ValueError
            self.failUnlessRaises(ValueError, boom)
        def testFailUnlessRaises1_fail(self):
            def boom():
                raise IndexError
            self.failUnlessRaises(ValueError, boom)
        def testFailUnlessRaises2_fail(self):
            def boom():
                pass
            self.failUnlessRaises(ValueError, boom)
        def testFailUnlessEqual_pass(self):
            self.failUnlessEqual(1, 1, "failed")
        def testFailUnlessEqual_fail(self):
            self.failUnlessEqual(1, 2, "failed")
        def testFailIfEqual_fail(self):
            self.failIfEqual(1, 1, "failed")
        def testFailIfEqual_pass(self):
            self.failIfEqual(1, 2, "failed")
        def testFailUnlessIdentical_pass(self):
            a = [1,2]
            b = a
            self.failUnlessIdentical(a, b, "failed")
        def testFailUnlessIdentical1_fail(self):
            a = [1,2]
            b = [1,2]
            self.failUnlessIdentical(a, b, "failed")
        def testFailUnlessIdentical2_fail(self):
            a = [1,2]
            b = [3,4]
            self.failUnlessIdentical(a, b, "failed")
        def testApproximates1_pass(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(a, b, .3, "failed")
        def testApproximates2_pass(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(b, a, .3, "failed")
        def testApproximates3_fail(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(a, b, .1, "failed")
        def testApproximates4_fail(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(b, a, .1, "failed")
        def testFailUnlessAlmostEqual_pass(self):
            a = 8.0000001
            b = 8.00000012
            self.failUnlessAlmostEqual(a, b, 7, "failed")
        def testFailUnlessAlmostEqual_fail(self):
            a = 0.0000001
            b = 0.0000010
            self.failUnlessAlmostEqual(a, b, 7, "failed")

        def testFailIfAlmostEqual_pass(self):
            a = 0.0000001
            b = 0.0000010
            self.failIfAlmostEqual(a, b, 7, "failed")

        def testFailIfAlmostEqual_fail(self):
            a = 8.0000001
            b = 8.00000012
            self.failIfAlmostEqual(a, b, 7, "failed")

        def testFailUnlessSubstring_pass(self):
            astring = "this is a string"
            substring = "this"
            failUnlessSubstring(substring, astring)

        def testFailUnlessSubstring_fail(self):
            astring = "this is a string"
            substring = "o/` batman!....batman! o/`"
            failUnlessSubstring(substring, astring)

        def testFailIfSubstring_pass(self):
            astring = "this is a string"
            substring = "o/` batman!....batman! o/`"
            failIfSubstring(substring, astring)

        def testFailIfSubstring_fail(self):
            astring = "this is a string"
            substring = "this"
            failIfSubstring(substring, astring)
            
        def testSkip1_skip(self):
            raise unittest.SkipTest("skip me")
        def testSkip2_skip(self):
            pass
        testSkip2_skip.skip = "skip me"
        def testTodo1_exfail(self):
            self.fail("deliberate failure")
        testTodo1_exfail.todo = "expected to fail"
        def testTodo2_exfail(self):
            raise ValueError
        testTodo2_exfail.todo = "expected to fail"
        def testTodo3_unexpass(self):
            pass # unexpected success
        testTodo3_unexpass.todo = "expected to fail"
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
        def testDeferred6_skip(self):
            pass
        testDeferred6_skip.skip = 'skip this test'
        def testDeferred7_exfail(self):
            return defer.fail(unittest.FailTest('you got an F!'))
        testDeferred7_exfail.todo = "i'm gonna get an F"
        def testDeferred8_exfail(self):
            return defer.fail(RuntimeError('you got another F!'))
        testDeferred8_exfail.todo = "I'm gonna get another F"
        def testDeferred9_unexpass(self):
            pass
        testDeferred9_unexpass.todo = "Holy shit! i didn't get an F!"
        
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

        def testNewStyleTodo1_exfail(self):
            raise RuntimeError, "expected failure"
        testNewStyleTodo1_exfail.todo = (RuntimeError, "this is an expected failure")
        def testNewStyleTodo2_exfail(self):
            raise RuntimeError, "expected failure"
        testNewStyleTodo2_exfail.todo = ((RuntimeError, OSError), "we expected as much")
        def testNewStyleTodo3_error(self):
            raise RuntimeError, "we had no idea!+"
        testNewStyleTodo3_error.todo = (OSError, "we expected something else")
        def testNewStyleTodo4_error(self):
            raise RuntimeError, "we had no idea!+"
        testNewStyleTodo4_error.todo = ((OSError, SyntaxError), "we expected something else")

        def testNewStyleTodoLoggedErr_exfail(self):
            try:
                1/0
            except:
                log.err()
        testNewStyleTodoLoggedErr_exfail.todo = (ZeroDivisionError, "need to learn that I can't divide by 0")

    class TestSkipClassAttr(unittest.TestCase):
        def testMethodSkipPrecedence_skipAttr(self):
            pass
        testMethodSkipPrecedence_skipAttr.skip = METHOD_SKIP_MSG
        def testClassSkipPrecedence_skipClassAttr(self):
            pass
    TestSkipClassAttr.skip = CLASS_SKIP_MSG

    class TestTodoClassAttr(unittest.TestCase):
        def testMethodTodoPrecedence_todoAttr(self):
            pass
        testMethodTodoPrecedence_todoAttr.todo = METHOD_TODO_MSG
        def testClassTodoPrecedence_todoClassAttr(self):
            pass
    TestTodoClassAttr.todo = CLASS_TODO_MSG

    def checkResults(self, method):
        def _dbg(msg):
            log.msg(iface=itrial.ITrialDebug, testTests=msg)

        tm = itrial.ITestMethod(method)

        failUnlessEqual(tm.countTestCases(), 1)       
        failUnlessEqual(tm.runs, 1)
        failUnless(tm.startTime > 0)
        #failUnless(tm.endTime > 0)   # failed tests don't have endTime set
        failUnless(tm.name, "tm.name not set")
        failUnless(tm.klass, "tm.klass not set")
        failUnless(tm.module, "tm.module not set")
        failUnless(tm.setUp, "tm.setUp not set")
        failUnless(tm.tearDown, "tm.tearDown not set")
        

        def _checkStatus(meth, status):
            statusmsg = "test did not return status %s, instead returned %s" % (status, meth.status)
            if meth.errors and status is not ERROR:
                statusmsg += "\n\n%s" % (''.join(["\t%s\n" % line for line in
                                                  ''.join([f.getTraceback() for f in meth.errors]
                                        ).split('\n')]))
            failUnlessEqual(meth.status, status, statusmsg)

        def _checkTimeoutError(meth):
            if meth.timeout is not None:
                failUnless(meth.hasTbs, 'method did not have tracebacks!')
                f = meth.errors[0]
                failUnlessEqual(f.type, defer.TimeoutError)

        try:
            failUnless(tm.startTime > 0.0, "%f not > 0.0" % (tm.startTime,))

            if tm.name.endswith("_pass"):
                _checkStatus(tm, SUCCESS)
                failIf(tm.todo)
                failIf(tm.hasTbs)
                failIf(tm.skip)

            elif tm.name.endswith("_fail"):
                _checkStatus(tm, FAILURE)
                _checkTimeoutError(tm)
                failIf(tm.skip)
                failIf(tm.errors)
                failUnless(tm.hasTbs)
                failUnless(len(tm.failures) == 1,
                           "%s had %d failures" % (tm.name,
                                                   len(tm.failures)))
            elif tm.name.endswith("_error"):
                _checkStatus(tm, ERROR)
                _checkTimeoutError(tm)
                failUnless(tm.hasTbs)
                failUnless(len(tm.errors) == 1,
                           "%s had %d errors" % (tm.name,
                                                 len(tm.errors)))

                # with new-style todos it's possible for a todoed method to
                # wind up counting as a ERROR
                # failIf(tm.todo)
                failIf(tm.skip)
                failIf(tm.failures)

            elif tm.name.endswith("_skip"):
                _checkStatus(tm, SKIP)
                failUnless(tm.skip, "skip reason not set")
                failIf(tm.todo)
                failIf(tm.errors)
                failIf(tm.failures)
                failIf(tm.hasTbs)

            elif tm.name.endswith("_exfail"):
                _checkStatus(tm, EXPECTED_FAILURE)
                _checkTimeoutError(tm)
                failUnless(tm.hasTbs)
                failUnless(tm.errors or tm.failures)
                failUnless(tm.todo)
                failIf(tm.skip)

            elif tm.name.endswith("_unexpass"):
                _checkStatus(tm, UNEXPECTED_SUCCESS)
                _checkTimeoutError(tm)
                failUnless(tm.todo)
                failIf(tm.skip)

            elif tm.name.endswith("_timeout"):
                failUnless(tm.errors, "tm.errors was %s" % (tm.errors,))
                expectedExc, f = tm.original.t_excClass, tm.errors[0]
                failUnless(f.check(expectedExc),
                           "exception '%s', with tb:\n%s\n\n was not of expected type '%s'" % (
                           f, f.getTraceback(), expectedExc))
                failUnlessEqual(f.value.args[0], tm.original.t_excArg)
                failUnlessEqual(itrial.ITimeout(tm.timeout).duration, tm.original.t_duration)

            elif tm.name.endswith("_timeoutClassAttr"):
                failUnless(tm.errors, "tm.errors was %s" % (tm.errors,))
                expectedExc, f = tm.klass.t_excClass, tm.errors[0]
                failUnless(f.check(expectedExc),
                           "exception '%s', with tb:\n%s\n\n was not of expected type '%s'" % (
                           f, f.getTraceback(), expectedExc))
                failUnlessEqual(f.value.args[0], tm.klass.t_excArg)
                failUnlessEqual(itrial.ITimeout(tm.timeout).duration, tm.klass.t_duration)

            elif tm.name.endswith("_skipClassAttr"):
                failUnlessEqual(tm.skip, CLASS_SKIP_MSG)

            elif tm.name.endswith("_skipAttr"):
                failUnlessEqual(tm.skip, METHOD_SKIP_MSG)

            elif tm.name.endswith("_todoClassAttr"):
                failUnlessEqual(tm.todo, CLASS_TODO_MSG)

            elif tm.name.endswith("_todoAttr"):
                failUnlessEqual(tm.todo, METHOD_TODO_MSG)

            else:
                raise unittest.FailTest, "didn't have tests for a method ending in %s" % (
                                         tm.name.split('_')[1],)
        except unittest.FailTest:
            tb = failure.Failure().getTraceback()
            raise unittest.FailTest, "error occured in test %s: %s" % (tm.name, tb)
        

    def testMethods(self):
        from twisted.trial.test.common import BogusReporter
        for klass in (self.Tests,
                      self.TestSkipClassAttr,
                      self.TestTodoClassAttr):
            suite = runner.TrialRoot(BogusReporter(), util._Janitor())
            suite.addTestClass(klass)
            suite.run()

            for method in suite.methods:
                try:
                    self.checkResults(method)
                except unittest.FailTest:
                    raise



