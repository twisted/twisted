# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>

from twisted.trial.unittest import TestCase

pyunit = __import__('unittest')

class TestPyUnitResult(TestCase):

    def test_success(self):
        class SuccessTest(TestCase):
            ran = False
            def test_foo(s):
                s.ran = True
        test = SuccessTest('test_foo')
        result = pyunit.TestResult()
        test.run(result)

        self.failUnless(test.ran)
        self.assertEqual(1, result.testsRun)
        self.failUnless(result.wasSuccessful())

    def test_failure(self):
        class FailureTest(TestCase):
            ran = False
            def test_foo(s):
                s.ran = True
                s.fail('boom!')
        test = FailureTest('test_foo')
        result = pyunit.TestResult()
        test.run(result)

        self.failUnless(test.ran)
        self.assertEqual(1, result.testsRun)
        self.assertEqual(1, len(result.failures))
        self.failIf(result.wasSuccessful())

    def test_error(self):
        class ErrorTest(TestCase):
            ran = False
            def test_foo(s):
                s.ran = True
                1/0
        test = ErrorTest('test_foo')
        result = pyunit.TestResult()
        test.run(result)

        self.failUnless(test.ran)
        self.assertEqual(1, result.testsRun)
        self.assertEqual(1, len(result.errors))
        self.failIf(result.wasSuccessful())

    def test_setUpError(self):
        class ErrorTest(TestCase):
            ran = False
            def setUp(self):
                1/0
            def test_foo(s):
                s.ran = True
        test = ErrorTest('test_foo')
        result = pyunit.TestResult()
        test.run(result)

        self.failIf(test.ran)
        self.assertEqual(1, result.testsRun)
        self.assertEqual(1, len(result.errors))
        self.failIf(result.wasSuccessful())

