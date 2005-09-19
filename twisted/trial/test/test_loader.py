from twisted.trial import unittest
from twisted.trial import runner, reporter

class LoaderTest(unittest.TestCase):
    def setUp(self):
        self.reporter = reporter.Reporter()
        self.loader = runner.TestLoader(self.reporter)

    def test_loadClass(self):
        import sample
        suite = self.loader.loadClass(sample.FooTest)
        self.failUnlessEqual(2, suite.countTestCases())
        self.failUnlessEqual([sample.FooTest.test_bar, sample.FooTest.test_foo],
                             [test.original for test in suite._tests])

    def test_loadModule(self):
        import sample
        suite = self.loader.loadModule(sample)
        self.failUnlessEqual(7, suite.countTestCases())
