# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for interrupting tests with Control-C.
"""

import StringIO

from twisted.trial import unittest
from twisted.trial import reporter, runner


class TrialTest(unittest.SynchronousTestCase):
    def setUp(self):
        self.output = StringIO.StringIO()
        self.reporter = reporter.TestResult()
        self.loader = runner.TestLoader()


class TestInterruptInTest(TrialTest):
    class InterruptedTest(unittest.TestCase):
        def test_02_raiseInterrupt(self):
            raise KeyboardInterrupt

        def test_01_doNothing(self):
            pass

        def test_03_doNothing(self):
            TestInterruptInTest.test_03_doNothing_run = True

    def setUp(self):
        super(TestInterruptInTest, self).setUp()
        self.suite = self.loader.loadClass(TestInterruptInTest.InterruptedTest)
        TestInterruptInTest.test_03_doNothing_run = None

    def test_setUpOK(self):
        self.assertEqual(3, self.suite.countTestCases())
        self.assertEqual(0, self.reporter.testsRun)
        self.failIf(self.reporter.shouldStop)

    def test_interruptInTest(self):
        runner.TrialSuite([self.suite]).run(self.reporter)
        self.failUnless(self.reporter.shouldStop)
        self.assertEqual(2, self.reporter.testsRun)
        self.failIf(TestInterruptInTest.test_03_doNothing_run,
                    "test_03_doNothing ran.")


class TestInterruptInSetUp(TrialTest):
    testsRun = 0

    class InterruptedTest(unittest.TestCase):
        def setUp(self):
            if TestInterruptInSetUp.testsRun > 0:
                raise KeyboardInterrupt

        def test_01(self):
            TestInterruptInSetUp.testsRun += 1

        def test_02(self):
            TestInterruptInSetUp.testsRun += 1
            TestInterruptInSetUp.test_02_run = True

    def setUp(self):
        super(TestInterruptInSetUp, self).setUp()
        self.suite = self.loader.loadClass(
            TestInterruptInSetUp.InterruptedTest)
        TestInterruptInSetUp.test_02_run = False
        TestInterruptInSetUp.testsRun = 0

    def test_setUpOK(self):
        self.assertEqual(0, TestInterruptInSetUp.testsRun)
        self.assertEqual(2, self.suite.countTestCases())
        self.assertEqual(0, self.reporter.testsRun)
        self.failIf(self.reporter.shouldStop)

    def test_interruptInSetUp(self):
        runner.TrialSuite([self.suite]).run(self.reporter)
        self.failUnless(self.reporter.shouldStop)
        self.assertEqual(2, self.reporter.testsRun)
        self.failIf(TestInterruptInSetUp.test_02_run,
                    "test_02 ran")


class TestInterruptInTearDown(TrialTest):
    testsRun = 0

    class InterruptedTest(unittest.TestCase):
        def tearDown(self):
            if TestInterruptInTearDown.testsRun > 0:
                raise KeyboardInterrupt

        def test_01(self):
            TestInterruptInTearDown.testsRun += 1

        def test_02(self):
            TestInterruptInTearDown.testsRun += 1
            TestInterruptInTearDown.test_02_run = True

    def setUp(self):
        super(TestInterruptInTearDown, self).setUp()
        self.suite = self.loader.loadClass(
            TestInterruptInTearDown.InterruptedTest)
        TestInterruptInTearDown.testsRun = 0
        TestInterruptInTearDown.test_02_run = False

    def test_setUpOK(self):
        self.assertEqual(0, TestInterruptInTearDown.testsRun)
        self.assertEqual(2, self.suite.countTestCases())
        self.assertEqual(0, self.reporter.testsRun)
        self.failIf(self.reporter.shouldStop)

    def test_interruptInTearDown(self):
        runner.TrialSuite([self.suite]).run(self.reporter)
        self.assertEqual(1, self.reporter.testsRun)
        self.failUnless(self.reporter.shouldStop)
        self.failIf(TestInterruptInTearDown.test_02_run,
                    "test_02 ran")
