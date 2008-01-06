# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python.compat import set
from twisted.trial import unittest, reporter, runner

_setUpClassRuns = 0
_tearDownClassRuns = 0

class NumberOfRuns(unittest.TestCase):
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
        
