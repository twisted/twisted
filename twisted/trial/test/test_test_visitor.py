from twisted.trial.unittest import TestCase
from twisted.trial.runner import TestLoader
from twisted.trial.test import common

class TestTestVisitor(TestCase):

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
        self.assertEqual(test_visitor.calls[0], ("suite", testCase))
        self.assertEqual(test_visitor.calls[1][0], "suite")
        self.assertEqual(test_visitor.calls[-1], ("suite_after", testCase))

    def test_visit_class_default(self):
        from twisted.trial.unittest import TestVisitor
        from twisted.trial.runner import ClassSuite
        testCase = self.loader.loadMethod(self.test_visit_class_default)
        test_visitor = TestVisitor()
        testCase.visit(test_visitor)

    def test_visit_class(self):
        from twisted.trial.runner import ClassSuite
        test_visitor = self.mock_visitor()
        testCase = self.loader.loadMethod(self.test_visit_class)
        testCase.visit(test_visitor)
        self.assertEqual(len(test_visitor.calls), 3)
        self.assertEqual(test_visitor.calls[0], ("suite", testCase))
        self.assertEqual(test_visitor.calls[1][0], "case")
        self.assertEqual(test_visitor.calls[2], ("suite_after", testCase))
