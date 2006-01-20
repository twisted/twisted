import StringIO

from twisted.python import reflect
from twisted.python.util import dsu
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
    """Tests for TestCase's assertion methods.  That is, failUnless*,
    failIf*, assert*.

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
        io = StringIO.StringIO()
        result = reporter.TestResult()
        test.run(result)
        self.failIf(result.wasSuccessful())
        self.failUnlessEqual(result.errors, [])
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


