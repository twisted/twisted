# -*- Python -*-

__version__ = "$Revision: 1.2 $"[11:-2]

from twisted.trial import unittest


class TestTraceback(unittest.TestCase):
    def testExtractTB(self):
        """Making sure unittest doesn't show up in traceback."""
        suite = unittest.TestSuite()
        testCase = self.FailingTest()
        reporter = unittest.Reporter()
        suite.runOneTest(testCase.__class__, testCase,
                         testCase.__class__.testThatWillFail,
                         reporter)
        klass, method, (eType, eVal, tb) = reporter.failures[0]
        stackList = unittest.extract_tb(tb)
        self.failUnlessEqual(len(stackList), 1)
        self.failUnlessEqual(stackList[0][2], 'testThatWillFail')

    # Hidden in here so the failing test doesn't get sucked into the bigsuite.
    class FailingTest(unittest.TestCase):
        def testThatWillFail(self):
            self.fail("Broken by design.")
