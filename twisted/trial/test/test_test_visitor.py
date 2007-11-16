from twisted.trial import unittest
from twisted.trial.runner import TestSuite, suiteVisit

pyunit = __import__('unittest')



class MockVisitor(object):
    def __init__(self):
        self.calls = []


    def __call__(self, testCase):
        self.calls.append(testCase)



class TestTestVisitor(unittest.TestCase):
    def setUp(self):
        self.visitor = MockVisitor()


    def test_visitCase(self):
        """
        Test that C{visit} works for a single test case.
        """
        testCase = TestTestVisitor('test_visitCase')
        testCase.visit(self.visitor)
        self.assertEqual(self.visitor.calls, [testCase])


    def test_visitSuite(self):
        """
        Test that C{visit} hits all tests in a suite.
        """
        tests = [TestTestVisitor('test_visitCase'),
                 TestTestVisitor('test_visitSuite')]
        testSuite = TestSuite(tests)
        testSuite.visit(self.visitor)
        self.assertEqual(self.visitor.calls, tests)


    def test_visitEmptySuite(self):
        """
        Test that C{visit} on an empty suite hits nothing.
        """
        TestSuite().visit(self.visitor)
        self.assertEqual(self.visitor.calls, [])


    def test_visitNestedSuite(self):
        """
        Test that C{visit} recurses through suites.
        """
        tests = [TestTestVisitor('test_visitCase'),
                 TestTestVisitor('test_visitSuite')]
        testSuite = TestSuite([TestSuite([test]) for test in tests])
        testSuite.visit(self.visitor)
        self.assertEqual(self.visitor.calls, tests)


    def test_visitPyunitSuite(self):
        """
        Test that C{suiteVisit} visits stdlib unittest suites
        """
        test = TestTestVisitor('test_visitPyunitSuite')
        suite = pyunit.TestSuite([test])
        suiteVisit(suite, self.visitor)
        self.assertEqual(self.visitor.calls, [test])


    def test_visitPyunitCase(self):
        """
        Test that a stdlib test case in a suite gets visited.
        """
        class PyunitCase(pyunit.TestCase):
            def test_foo(self):
                pass
        test = PyunitCase('test_foo')
        TestSuite([test]).visit(self.visitor)
        self.assertEqual(
            [call.id() for call in self.visitor.calls], [test.id()])
