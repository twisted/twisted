# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for Trial's C{setUpClass}, C{setUp}, C{tearDownClass}, and C{tearDown}.
"""

from twisted.python.compat import set
from twisted.trial import unittest, reporter, runner
from twisted.python import deprecate

_setUpClassRuns = 0
_tearDownClassRuns = 0

class NumberOfRuns(unittest.TestCase):
    """
    Test that C{setUpClass} and C{tearDownClass} are each run run only once for
    this class.
    """
    _suppressUpDownWarning = True

    def setUpClass(self):
        global _setUpClassRuns
        _setUpClassRuns += 1

    def test_1(self):
        global _setUpClassRuns
        self.failUnlessEqual(_setUpClassRuns, 1)

    def test_2(self):
        global _setUpClassRuns
        self.failUnlessEqual(_setUpClassRuns, 1)

    def test_3(self):
        global _setUpClassRuns
        self.failUnlessEqual(_setUpClassRuns, 1)

    def tearDownClass(self):
        global _tearDownClassRuns
        self.failUnlessEqual(_tearDownClassRuns, 0)
        _tearDownClassRuns += 1


class AttributeSetUp(unittest.TestCase):
    """
    Test that an attribute set in C{setUpClass} is available in C{setUp} and in
    each test method.
    """
    _suppressUpDownWarning = True

    def setUpClass(self):
        self.x = 42

    def setUp(self):
        self.failUnless(hasattr(self, 'x'), "Attribute 'x' not set")
        self.failUnlessEqual(self.x, 42)

    def test_1(self):
        self.failUnlessEqual(self.x, 42) # still the same

    def test_2(self):
        self.failUnlessEqual(self.x, 42) # still the same

    def tearDown(self):
        self.failUnlessEqual(self.x, 42) # still the same

    def tearDownClass(self):
        self.x = None


class AttributeManipulation(unittest.TestCase):
    """
    Test that attributes set in test methods are accessible in C{tearDown} and
    C{tearDownClass}.
    """
    _suppressUpDownWarning = True

    def setUpClass(self):
        self.testsRun = 0

    def test_1(self):
        self.testsRun += 1

    def test_2(self):
        self.testsRun += 1

    def test_3(self):
        self.testsRun += 1

    def tearDown(self):
        self.failUnless(self.testsRun > 0)

    def tearDownClass(self):
        self.failUnlessEqual(self.testsRun, 3)


class AttributeSharing(unittest.TestCase):
    class AttributeSharer(unittest.TestCase):
        def test_1(self):
            self.first = 'test1Run'

        def test_2(self):
            self.failIf(hasattr(self, 'first'))

    class ClassAttributeSharer(AttributeSharer):
        _suppressUpDownWarning = True

        def setUpClass(self):
            pass

        def test_3(self):
            self.failUnlessEqual('test1Run', self.first)

    def setUp(self):
        self.loader = runner.TestLoader()

    def test_normal(self):
        result = reporter.TestResult()
        suite = self.loader.loadClass(AttributeSharing.AttributeSharer)
        suite.run(result)
        self.failUnlessEqual(result.errors, [])
        self.failUnlessEqual(result.failures, [])

    def test_shared(self):
        result = reporter.TestResult()
        suite = self.loader.loadClass(AttributeSharing.ClassAttributeSharer)
        suite.run(result)
        self.failUnlessEqual(result.errors, [])
        self.failUnlessEqual(len(result.failures), 1) # from test_2
        self.failUnlessEqual(result.failures[0][0].shortDescription(),
                             'test_2')


class FactoryCounting(unittest.TestCase):
    class MyTestCase(unittest.TestCase):
        _suppressUpDownWarning = True

        _setUpClassRun = 0
        _tearDownClassRun = 0
        def setUpClass(self):
            self.__class__._setUpClassRun += 1

        def test_1(self):
            pass

        def test_2(self):
            pass

        def tearDownClass(self):
            self.__class__._tearDownClassRun += 1

    class AnotherTestCase(MyTestCase):
        _suppressUpDownWarning = True

        _setUpClassRun = 0
        _tearDownClassRun = 0
        def setUpClass(self):
            self.__class__._setUpClassRun += 1
            raise unittest.SkipTest('reason')

        def test_1(self):
            pass

        def test_2(self):
            pass

        def tearDownClass(self):
            self.__class__._tearDownClassRun += 1


    def setUp(self):
        self.factory = FactoryCounting.MyTestCase
        self.subFactory = FactoryCounting.AnotherTestCase
        self._reset()

    def _reset(self):
        self.factory._setUpClassRun = self.factory._tearDownClassRun = 0
        self.subFactory._setUpClassRun = self.subFactory._tearDownClassRun = 0
        self.factory._instances = set()
        self.factory._instancesRun = set()

    def test_createAndRun(self):
        test = self.factory('test_1')
        self.failUnlessEqual(test._isFirst(), True)
        result = reporter.TestResult()
        test(result)
        self.failUnlessEqual(self.factory._setUpClassRun, 1)
        self.failUnlessEqual(self.factory._tearDownClassRun, 1)

    def test_createTwoAndRun(self):
        tests = map(self.factory, ['test_1', 'test_2'])
        self.failUnlessEqual(tests[0]._isFirst(), True)
        self.failUnlessEqual(tests[1]._isFirst(), True)
        result = reporter.TestResult()
        tests[0](result)
        self.failUnlessEqual(self.factory._setUpClassRun, 1)
        self.failUnlessEqual(self.factory._tearDownClassRun, 0)
        tests[1](result)
        self.failUnlessEqual(self.factory._setUpClassRun, 1)
        self.failUnlessEqual(self.factory._tearDownClassRun, 1)

    def test_runTwice(self):
        test = self.factory('test_1')
        result = reporter.TestResult()
        test(result)
        self.failUnlessEqual(self.factory._setUpClassRun, 1)
        self.failUnlessEqual(self.factory._tearDownClassRun, 1)
        test(result)
        self.failUnlessEqual(self.factory._setUpClassRun, 2)
        self.failUnlessEqual(self.factory._tearDownClassRun, 2)


    def test_hashability(self):
        """
        In order for one test method to be runnable twice, two TestCase
        instances with the same test method name must not compare as equal.
        """
        first = self.factory('test_1')
        second = self.factory('test_1')
        self.assertTrue(first == first)
        self.assertTrue(first != second)
        self.assertFalse(first == second)
        # Just to make sure
        container = {}
        container[first] = None
        container[second] = None
        self.assertEqual(len(container), 2)


    def test_runMultipleCopies(self):
        tests = map(self.factory, ['test_1', 'test_1'])
        result = reporter.TestResult()
        tests[0](result)
        self.failUnlessEqual(self.factory._setUpClassRun, 1)
        self.failUnlessEqual(self.factory._tearDownClassRun, 0)
        tests[1](result)
        self.failUnlessEqual(self.factory._setUpClassRun, 1)
        self.failUnlessEqual(self.factory._tearDownClassRun, 1)

    def test_skippingSetUpClass(self):
        tests = map(self.subFactory, ['test_1', 'test_2'])
        result = reporter.TestResult()
        tests[0](result)
        self.failUnlessEqual(self.subFactory._setUpClassRun, 1)
        self.failUnlessEqual(self.subFactory._tearDownClassRun, 0)
        tests[1](result)
        self.failUnlessEqual(self.subFactory._setUpClassRun, 2)
        self.failUnlessEqual(self.subFactory._tearDownClassRun, 0)



class Deprecation(unittest.TestCase):
    """
    L{TestCase.setUpClass} and L{TestCase.tearDownClass} are deprecated and a
    L{DeprecationWarning} is emitted when they are encountered.
    """
    def _classDeprecation(self, cls, methodName):
        test = cls()
        result = reporter.TestResult()
        original = deprecate.getWarningMethod()
        self.addCleanup(deprecate.setWarningMethod, original)
        warnings = []
        # XXX deprecate.collectWarnings()?  Maybe with support for filtering.
        deprecate.setWarningMethod(
            lambda message, category, stacklevel: warnings.append((
                    message, category, stacklevel)))
        test(result)
        message, category, stacklevel = warnings[0]
        self.assertIdentical(category, DeprecationWarning)
        self.assertEqual(
            message,
            methodName + ", deprecated since Twisted 8.2.0, was overridden "
            "by " + cls.__module__ + "." + cls.__name__ + ".  Use " +
            methodName.replace('Class', '') + " instead.")


    def test_setUpClassDeprecation(self):
        """
        A L{DeprecationWarning} is emitted when a L{TestCase} with an
        overridden C{setUpClass} method is run.
        """
        class SetUpClassUser(unittest.TestCase):
            def setUpClass(self):
                pass
        self._classDeprecation(SetUpClassUser, 'setUpClass')


    def test_tearDownClassDeprecation(self):
        """
        A L{DeprecationWarning} is emitted when a L{TestCase} with an
        overridden C{tearDownClass} method is run.
        """
        class TearDownClassUser(unittest.TestCase):
            def tearDownClass(self):
                pass
        self._classDeprecation(TearDownClassUser, 'tearDownClass')
