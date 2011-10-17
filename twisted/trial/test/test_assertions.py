# Copyright (c) 2001-2011 Twisted Matrix Laboratories.
# See LICENSE for details

"""
Tests for assertions provided by L{twisted.trial.unittest.TestCase}.
"""

import warnings
from pprint import pformat

from twisted.python import reflect, failure
from twisted.python.deprecate import deprecated, getVersionString
from twisted.python.versions import Version
from twisted.internet import defer
from twisted.trial import unittest, runner, reporter

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
    """
    Tests for TestCase's assertion methods.  That is, failUnless*,
    failIf*, assert*.

    Note: As of 11.2, assertEqual is preferred over the failUnlessEqual(s)
    variants.  Tests have been modified to reflect this preference.

    This is pretty paranoid.  Still, a certain paranoia is healthy if you
    are testing a unit testing framework.
    """

    class FailingTest(unittest.TestCase):
        def test_fails(self):
            raise self.failureException()

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
        result = reporter.TestResult()
        test.run(result)
        self.failIf(result.wasSuccessful())
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)

    def test_failIf(self):
        for notTrue in [0, 0.0, False, None, (), []]:
            self.failIf(notTrue, "failed on %r" % (notTrue,))
        for true in [1, True, 'cat', [1,2], (3,4)]:
            try:
                self.failIf(true, "failed on %r" % (true,))
            except self.failureException, e:
                self.assertEqual(str(e), "failed on %r" % (true,))
            else:
                self.fail("Call to failIf(%r) didn't fail" % (true,))

    def test_failUnless(self):
        for notTrue in [0, 0.0, False, None, (), []]:
            try:
                self.failUnless(notTrue, "failed on %r" % (notTrue,))
            except self.failureException, e:
                self.assertEqual(str(e), "failed on %r" % (notTrue,))
            else:
                self.fail("Call to failUnless(%r) didn't fail" % (notTrue,))
        for true in [1, True, 'cat', [1,2], (3,4)]:
            self.failUnless(true, "failed on %r" % (true,))


    def _testEqualPair(self, first, second):
        x = self.assertEqual(first, second)
        if x != first:
            self.fail("assertEqual should return first parameter")


    def _testUnequalPair(self, first, second):
        try:
            self.assertEqual(first, second)
        except self.failureException, e:
            expected = 'not equal:\na = %s\nb = %s\n' % (
                pformat(first), pformat(second))
            if str(e) != expected:
                self.fail("Expected: %r; Got: %s" % (expected, str(e)))
        else:
            self.fail("Call to assertEqual(%r, %r) didn't fail"
                      % (first, second))


    def test_assertEqual_basic(self):
        self._testEqualPair('cat', 'cat')
        self._testUnequalPair('cat', 'dog')
        self._testEqualPair([1], [1])
        self._testUnequalPair([1], 'orange')


    def test_assertEqual_custom(self):
        x = MockEquality('first')
        y = MockEquality('second')
        z = MockEquality('fecund')
        self._testEqualPair(x, x)
        self._testEqualPair(x, z)
        self._testUnequalPair(x, y)
        self._testUnequalPair(y, z)


    def test_assertEqualMessage(self):
        """
        When a message is passed to L{assertEqual}, it is included in the
        error message.
        """
        exception = self.assertRaises(
            self.failureException, self.assertEqual,
            'foo', 'bar', 'message')
        self.assertEqual(
            str(exception),
            "message\nnot equal:\na = 'foo'\nb = 'bar'\n")


    def test_assertEqualNoneMessage(self):
        """
        If a message is specified as C{None}, it is not included in the error
        message of L{assertEqual}.
        """
        exception = self.assertRaises(
            self.failureException, self.assertEqual, 'foo', 'bar', None)
        self.assertEqual(str(exception), "not equal:\na = 'foo'\nb = 'bar'\n")


    def test_assertEqual_incomparable(self):
        apple = MockEquality('apple')
        orange = ['orange']
        try:
            self.assertEqual(apple, orange)
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
        except self.failureException:
            # what we expect
            pass
        else:
            self.fail("Expected exception wasn't raised. Should have failed")

    def test_failUnlessRaises_noException(self):
        try:
            self.failUnlessRaises(ValueError, lambda : None)
        except self.failureException, e:
            self.assertEqual(str(e),
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
        except self.failureException:
            # what we expect
            pass
        else:
            self.fail("Should have raised exception")

    def test_failIfEqual_basic(self):
        x, y, z = [1], [2], [1]
        ret = self.failIfEqual(x, y)
        self.assertEqual(ret, x,
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
        self.assertEqual(ret, x,
                             "failIfEqual should return first parameter")
        self.failUnlessRaises(self.failureException,
                              self.failIfEqual, x, x)
        # test when __ne__ is not defined
        self.failIfEqual(x, z, "__ne__ not defined, so not equal")

    def test_failUnlessIdentical(self):
        x, y, z = [1], [1], [2]
        ret = self.failUnlessIdentical(x, x)
        self.assertEqual(ret, x,
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
        self.assertEqual(ret, x, "failUnlessApproximates should return "
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
        self.assertEqual(ret, x, "failUnlessAlmostEqual should return "
                             "first parameter (%r, %r)" % (ret, x))
        self.failUnlessRaises(self.failureException,
                              self.failUnlessAlmostEqual, x, y, precision)

    def test_failIfAlmostEqual(self):
        precision = 5
        x = 8.000001
        y = 8.00001
        z = 8.000002
        ret = self.failIfAlmostEqual(x, y, precision)
        self.assertEqual(ret, x, "failIfAlmostEqual should return "
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
        self.assertEqual(ret, x, 'should return first parameter')
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
        self.assertEqual(ret, x, 'should return first parameter')
        self.failUnlessRaises(self.failureException,
                              self.failIfSubstring, x, x)
        self.failUnlessRaises(self.failureException,
                              self.failIfSubstring, x, z)

    def test_assertFailure(self):
        d = defer.maybeDeferred(lambda: 1/0)
        return self.assertFailure(d, ZeroDivisionError)

    def test_assertFailure_wrongException(self):
        d = defer.maybeDeferred(lambda: 1/0)
        self.assertFailure(d, OverflowError)
        d.addCallbacks(lambda x: self.fail('Should have failed'),
                       lambda x: x.trap(self.failureException))
        return d

    def test_assertFailure_noException(self):
        d = defer.succeed(None)
        self.assertFailure(d, ZeroDivisionError)
        d.addCallbacks(lambda x: self.fail('Should have failed'),
                       lambda x: x.trap(self.failureException))
        return d

    def test_assertFailure_moreInfo(self):
        """
        In the case of assertFailure failing, check that we get lots of
        information about the exception that was raised.
        """
        try:
            1/0
        except ZeroDivisionError:
            f = failure.Failure()
            d = defer.fail(f)
        d = self.assertFailure(d, RuntimeError)
        d.addErrback(self._checkInfo, f)
        return d

    def _checkInfo(self, assertionFailure, f):
        assert assertionFailure.check(self.failureException)
        output = assertionFailure.getErrorMessage()
        self.assertIn(f.getErrorMessage(), output)
        self.assertIn(f.getBriefTraceback(), output)

    def test_assertFailure_masked(self):
        """
        A single wrong assertFailure should fail the whole test.
        """
        class ExampleFailure(Exception):
            pass

        class TC(unittest.TestCase):
            failureException = ExampleFailure
            def test_assertFailure(self):
                d = defer.maybeDeferred(lambda: 1/0)
                self.assertFailure(d, OverflowError)
                self.assertFailure(d, ZeroDivisionError)
                return d

        test = TC('test_assertFailure')
        result = reporter.TestResult()
        test.run(result)
        self.assertEqual(1, len(result.failures))


    def test_assertWarns(self):
        """
        Test basic assertWarns report.
        """
        def deprecated(a):
            warnings.warn("Woo deprecated", category=DeprecationWarning)
            return a
        r = self.assertWarns(DeprecationWarning, "Woo deprecated", __file__,
            deprecated, 123)
        self.assertEqual(r, 123)


    def test_assertWarnsRegistryClean(self):
        """
        Test that assertWarns cleans the warning registry, so the warning is
        not swallowed the second time.
        """
        def deprecated(a):
            warnings.warn("Woo deprecated", category=DeprecationWarning)
            return a
        r1 = self.assertWarns(DeprecationWarning, "Woo deprecated", __file__,
            deprecated, 123)
        self.assertEqual(r1, 123)
        # The warning should be raised again
        r2 = self.assertWarns(DeprecationWarning, "Woo deprecated", __file__,
            deprecated, 321)
        self.assertEqual(r2, 321)


    def test_assertWarnsError(self):
        """
        Test assertWarns failure when no warning is generated.
        """
        def normal(a):
            return a
        self.assertRaises(self.failureException,
            self.assertWarns, DeprecationWarning, "Woo deprecated", __file__,
            normal, 123)


    def test_assertWarnsWrongCategory(self):
        """
        Test assertWarns failure when the category is wrong.
        """
        def deprecated(a):
            warnings.warn("Foo deprecated", category=DeprecationWarning)
            return a
        self.assertRaises(self.failureException,
            self.assertWarns, UserWarning, "Foo deprecated", __file__,
            deprecated, 123)


    def test_assertWarnsWrongMessage(self):
        """
        Test assertWarns failure when the message is wrong.
        """
        def deprecated(a):
            warnings.warn("Foo deprecated", category=DeprecationWarning)
            return a
        self.assertRaises(self.failureException,
            self.assertWarns, DeprecationWarning, "Bar deprecated", __file__,
            deprecated, 123)


    def test_assertWarnsWrongFile(self):
        """
        If the warning emitted by a function refers to a different file than is
        passed to C{assertWarns}, C{failureException} is raised.
        """
        def deprecated(a):
            # stacklevel=2 points at the direct caller of the function.  The
            # way assertRaises is invoked below, the direct caller will be
            # something somewhere in trial, not something in this file.  In
            # Python 2.5 and earlier, stacklevel of 0 resulted in a warning
            # pointing to the warnings module itself.  Starting in Python 2.6,
            # stacklevel of 0 and 1 both result in a warning pointing to *this*
            # file, presumably due to the fact that the warn function is
            # implemented in C and has no convenient Python
            # filename/linenumber.
            warnings.warn(
                "Foo deprecated", category=DeprecationWarning, stacklevel=2)
        self.assertRaises(
            self.failureException,
            # Since the direct caller isn't in this file, try to assert that
            # the warning *does* point to this file, so that assertWarns raises
            # an exception.
            self.assertWarns, DeprecationWarning, "Foo deprecated", __file__,
            deprecated, 123)

    def test_assertWarnsOnClass(self):
        """
        Test assertWarns works when creating a class instance.
        """
        class Warn:
            def __init__(self):
                warnings.warn("Do not call me", category=RuntimeWarning)
        r = self.assertWarns(RuntimeWarning, "Do not call me", __file__,
            Warn)
        self.assertTrue(isinstance(r, Warn))
        r = self.assertWarns(RuntimeWarning, "Do not call me", __file__,
            Warn)
        self.assertTrue(isinstance(r, Warn))


    def test_assertWarnsOnMethod(self):
        """
        Test assertWarns works when used on an instance method.
        """
        class Warn:
            def deprecated(self, a):
                warnings.warn("Bar deprecated", category=DeprecationWarning)
                return a
        w = Warn()
        r = self.assertWarns(DeprecationWarning, "Bar deprecated", __file__,
            w.deprecated, 321)
        self.assertEqual(r, 321)
        r = self.assertWarns(DeprecationWarning, "Bar deprecated", __file__,
            w.deprecated, 321)
        self.assertEqual(r, 321)


    def test_assertWarnsOnCall(self):
        """
        Test assertWarns works on instance with C{__call__} method.
        """
        class Warn:
            def __call__(self, a):
                warnings.warn("Egg deprecated", category=DeprecationWarning)
                return a
        w = Warn()
        r = self.assertWarns(DeprecationWarning, "Egg deprecated", __file__,
            w, 321)
        self.assertEqual(r, 321)
        r = self.assertWarns(DeprecationWarning, "Egg deprecated", __file__,
            w, 321)
        self.assertEqual(r, 321)


    def test_assertWarnsFilter(self):
        """
        Test assertWarns on a warning filterd by default.
        """
        def deprecated(a):
            warnings.warn("Woo deprecated", category=PendingDeprecationWarning)
            return a
        r = self.assertWarns(PendingDeprecationWarning, "Woo deprecated",
            __file__, deprecated, 123)
        self.assertEqual(r, 123)


    def test_assertWarnsMultipleWarnings(self):
        """
        C{assertWarns} does not raise an exception if the function it is passed
        triggers the same warning more than once.
        """
        def deprecated():
            warnings.warn("Woo deprecated", category=PendingDeprecationWarning)
        def f():
            deprecated()
            deprecated()
        self.assertWarns(
            PendingDeprecationWarning, "Woo deprecated", __file__, f)


    def test_assertWarnsDifferentWarnings(self):
        """
        For now, assertWarns is unable to handle multiple different warnings,
        so it should raise an exception if it's the case.
        """
        def deprecated(a):
            warnings.warn("Woo deprecated", category=DeprecationWarning)
            warnings.warn("Another one", category=PendingDeprecationWarning)
        e = self.assertRaises(self.failureException,
                self.assertWarns, DeprecationWarning, "Woo deprecated",
                __file__, deprecated, 123)
        self.assertEqual(str(e), "Can't handle different warnings")


    def test_assertWarnsAfterUnassertedWarning(self):
        """
        Warnings emitted before L{TestCase.assertWarns} is called do not get
        flushed and do not alter the behavior of L{TestCase.assertWarns}.
        """
        class TheWarning(Warning):
            pass

        def f(message):
            warnings.warn(message, category=TheWarning)
        f("foo")
        self.assertWarns(TheWarning, "bar", __file__, f, "bar")
        [warning] = self.flushWarnings([f])
        self.assertEqual(warning['message'], "foo")


    def test_assertIsInstance(self):
        """
        Test a true condition of assertIsInstance.
        """
        A = type('A', (object,), {})
        a = A()
        self.assertIsInstance(a, A)

    def test_assertIsInstanceMultipleClasses(self):
        """
        Test a true condition of assertIsInstance with multiple classes.
        """
        A = type('A', (object,), {})
        B = type('B', (object,), {})
        a = A()
        self.assertIsInstance(a, (A, B))

    def test_assertIsInstanceError(self):
        """
        Test an error with assertIsInstance.
        """
        A = type('A', (object,), {})
        B = type('B', (object,), {})
        a = A()
        self.assertRaises(self.failureException, self.assertIsInstance, a, B)

    def test_assertIsInstanceErrorMultipleClasses(self):
        """
        Test an error with assertIsInstance and multiple classes.
        """
        A = type('A', (object,), {})
        B = type('B', (object,), {})
        C = type('C', (object,), {})
        a = A()
        self.assertRaises(self.failureException, self.assertIsInstance, a, (B, C))


    def test_assertIsInstanceCustomMessage(self):
        """
        If L{TestCase.assertIsInstance} is passed a custom message as its 3rd
        argument, the message is included in the failure exception raised when
        the assertion fails.
        """
        exc = self.assertRaises(
            self.failureException,
            self.assertIsInstance, 3, str, "Silly assertion")
        self.assertIn("Silly assertion", str(exc))


    def test_assertNotIsInstance(self):
        """
        Test a true condition of assertNotIsInstance.
        """
        A = type('A', (object,), {})
        B = type('B', (object,), {})
        a = A()
        self.assertNotIsInstance(a, B)

    def test_assertNotIsInstanceMultipleClasses(self):
        """
        Test a true condition of assertNotIsInstance and multiple classes.
        """
        A = type('A', (object,), {})
        B = type('B', (object,), {})
        C = type('C', (object,), {})
        a = A()
        self.assertNotIsInstance(a, (B, C))

    def test_assertNotIsInstanceError(self):
        """
        Test an error with assertNotIsInstance.
        """
        A = type('A', (object,), {})
        a = A()
        error = self.assertRaises(self.failureException,
                                  self.assertNotIsInstance, a, A)
        self.assertEqual(str(error), "%r is an instance of %s" % (a, A))


    def test_assertNotIsInstanceErrorMultipleClasses(self):
        """
        Test an error with assertNotIsInstance and multiple classes.
        """
        A = type('A', (object,), {})
        B = type('B', (object,), {})
        a = A()
        self.assertRaises(self.failureException, self.assertNotIsInstance, a, (A, B))


    def test_assertDictEqual(self):
        """
        L{twisted.trial.unittest.TestCase} supports the C{assertDictEqual}
        method inherited from the standard library in Python 2.7.
        """
        self.assertDictEqual({'a': 1}, {'a': 1})
    if getattr(unittest.TestCase, 'assertDictEqual', None) is None:
        test_assertDictEqual.skip = (
            "assertDictEqual is not available on this version of Python")



class TestAssertionNames(unittest.TestCase):
    """
    Tests for consistency of naming within TestCase assertion methods
    """
    def _getAsserts(self):
        dct = {}
        reflect.accumulateMethods(self, dct, 'assert')
        return [ dct[k] for k in dct if not k.startswith('Not') and k != '_' ]

    def _name(self, x):
        return x.__name__


    def test_failUnlessMatchesAssert(self):
        """
        The C{failUnless*} test methods are a subset of the C{assert*} test
        methods.  This is intended to ensure that methods using the
        I{failUnless} naming scheme are not added without corresponding methods
        using the I{assert} naming scheme.  The I{assert} naming scheme is
        preferred, and new I{assert}-prefixed methods may be added without
        corresponding I{failUnless}-prefixed methods.
        """
        asserts = set(self._getAsserts())
        failUnlesses = set(reflect.prefixedMethods(self, 'failUnless'))
        self.assertEqual(
            failUnlesses, asserts.intersection(failUnlesses))


    def test_failIf_matches_assertNot(self):
        asserts = reflect.prefixedMethods(unittest.TestCase, 'assertNot')
        failIfs = reflect.prefixedMethods(unittest.TestCase, 'failIf')
        self.assertEqual(sorted(asserts, key=self._name),
                             sorted(failIfs, key=self._name))

    def test_equalSpelling(self):
        for name, value in vars(self).items():
            if not callable(value):
                continue
            if name.endswith('Equal'):
                self.failUnless(hasattr(self, name+'s'),
                                "%s but no %ss" % (name, name))
                self.assertEqual(value, getattr(self, name+'s'))
            if name.endswith('Equals'):
                self.failUnless(hasattr(self, name[:-1]),
                                "%s but no %s" % (name, name[:-1]))
                self.assertEqual(value, getattr(self, name[:-1]))


class TestCallDeprecated(unittest.TestCase):
    """
    Test use of the L{TestCase.callDeprecated} method with version objects.
    """

    version = Version('Twisted', 8, 0, 0)

    def test_callDeprecatedSuppressesWarning(self):
        """
        callDeprecated calls a deprecated callable, suppressing the
        deprecation warning.
        """
        self.callDeprecated(self.version, oldMethod, 'foo')
        self.assertEqual(
            self.flushWarnings(), [], "No warnings should be shown")


    def test_callDeprecatedCallsFunction(self):
        """
        L{callDeprecated} actually calls the callable passed to it, and
        forwards the result.
        """
        result = self.callDeprecated(self.version, oldMethod, 'foo')
        self.assertEqual('foo', result)


    def test_failsWithoutDeprecation(self):
        """
        L{callDeprecated} raises a test failure if the callable is not
        deprecated.
        """
        def notDeprecated():
            pass
        exception = self.assertRaises(
            self.failureException,
            self.callDeprecated, self.version, notDeprecated)
        self.assertEqual(
            "%r is not deprecated." % notDeprecated, str(exception))


    def test_failsWithIncorrectDeprecation(self):
        """
        callDeprecated raises a test failure if the callable was deprecated
        at a different version to the one expected.
        """
        differentVersion = Version('Foo', 1, 2, 3)
        exception = self.assertRaises(
            self.failureException,
            self.callDeprecated,
            differentVersion, oldMethod, 'foo')
        self.assertIn(getVersionString(self.version), str(exception))
        self.assertIn(getVersionString(differentVersion), str(exception))


    def test_nestedDeprecation(self):
        """
        L{callDeprecated} ignores all deprecations apart from the first.

        Multiple warnings are generated when a deprecated function calls
        another deprecated function. The first warning is the one generated by
        the explicitly called function. That's the warning that we care about.
        """
        differentVersion = Version('Foo', 1, 2, 3)

        def nestedDeprecation(*args):
            return oldMethod(*args)
        nestedDeprecation = deprecated(differentVersion)(nestedDeprecation)

        self.callDeprecated(differentVersion, nestedDeprecation, 24)

        # The oldMethod deprecation should have been emitted too, not captured
        # by callDeprecated.  Flush it now to make sure it did happen and to
        # prevent it from showing up on stdout.
        warningsShown = self.flushWarnings()
        self.assertEqual(len(warningsShown), 1)


    def test_callDeprecationWithMessage(self):
        """
        L{callDeprecated} can take a message argument used to check the warning
        emitted.
        """
        self.callDeprecated((self.version, "newMethod"),
                            oldMethodReplaced, 1)


    def test_callDeprecationWithWrongMessage(self):
        """
        If the message passed to L{callDeprecated} doesn't match,
        L{callDeprecated} raises a test failure.
        """
        exception = self.assertRaises(
            self.failureException,
            self.callDeprecated,
            (self.version, "something.wrong"),
            oldMethodReplaced, 1)
        self.assertIn(getVersionString(self.version), str(exception))
        self.assertIn("please use newMethod instead", str(exception))




@deprecated(TestCallDeprecated.version)
def oldMethod(x):
    """
    Deprecated method for testing.
    """
    return x


@deprecated(TestCallDeprecated.version, replacement="newMethod")
def oldMethodReplaced(x):
    """
    Another deprecated method, which has been deprecated in favor of the
    mythical 'newMethod'.
    """
    return 2 * x
