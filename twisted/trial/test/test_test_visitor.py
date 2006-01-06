from twisted.trial import unittest
from twisted.trial.runner import TestLoader


class TestTestVisitor(unittest.TestCase):

    def setUp(self):
        self.loader = TestLoader()
        try:
            from twisted.trial.unittest import TestVisitor
            class MockVisitor(TestVisitor):
                def __init__(self):
                    self.calls = []
                def visitCase(self, testCase):
                    self.calls.append(("case", testCase))
                def visitSuite(self, testModule):
                    self.calls.append(("suite", testModule))
                def visitSuiteAfter(self, testModule):
                    self.calls.append(("suite_after", testModule))
            self.mock_visitor = MockVisitor
        except ImportError:
            pass

    def test_imports(self):
        from twisted.trial.unittest import TestVisitor

    def test_visit_case_default(self):
        from twisted.trial.unittest import TestVisitor
        testCase = self.loader.loadMethod(self.test_visit_case_default)
        test_visitor = TestVisitor()
        testCase.visit(test_visitor)

    def test_visit_case(self):
        testCase = TestTestVisitor('test_visit_case')
        test_visitor = self.mock_visitor()
        testCase.visit(test_visitor)
        self.assertEqual(test_visitor.calls, [("case", testCase)])

    def test_visit_module_default(self):
        from twisted.trial.unittest import TestVisitor
        import sys
        testCase = self.loader.loadModule(sys.modules[__name__])
        test_visitor = TestVisitor()
        testCase.visit(test_visitor)

    def test_visit_module(self):
        import sys
        test_visitor = self.mock_visitor()
        testCase = self.loader.loadModule(sys.modules[__name__])
        testCase.visit(test_visitor)
        self.failIf(len(test_visitor.calls) < 5, str(test_visitor.calls))
        self.assertEqual(test_visitor.calls[1][0], "case")

    def test_visit_class_default(self):
        from twisted.trial.unittest import TestVisitor
        testCase = self.loader.loadMethod(self.test_visit_class_default)
        test_visitor = TestVisitor()
        testCase.visit(test_visitor)

    def test_visit_class(self):
        test_visitor = self.mock_visitor()
        testCase = self.loader.loadMethod(self.test_visit_class)
        testCase.visit(test_visitor)
        self.assertEqual(len(test_visitor.calls), 1)
        self.assertEqual(test_visitor.calls[0][0], "case")
