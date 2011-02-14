# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Direct unit tests for L{twisted.trial.unittest.TestCase}.
"""

from twisted.trial.unittest import TestCase


class TestCaseTests(TestCase):
    """
    L{TestCase} tests.
    """
    class MyTestCase(TestCase):
        """
        Some test methods which can be used to test behaviors of
        L{TestCase}.
        """
        def test_1(self):
            pass

    def setUp(self):
        """
        Create a couple instances of C{MyTestCase}, each for the same test
        method, to be used in the test methods of this class.
        """
        self.first = self.MyTestCase('test_1')
        self.second = self.MyTestCase('test_1')


    def test_equality(self):
        """
        In order for one test method to be runnable twice, two TestCase
        instances with the same test method name must not compare as equal.
        """
        self.assertTrue(self.first == self.first)
        self.assertTrue(self.first != self.second)
        self.assertFalse(self.first == self.second)
        

    def test_hashability(self):
        """
        In order for one test method to be runnable twice, two TestCase
        instances with the same test method name should not have the same
        hash value.
        """
        container = {}
        container[self.first] = None
        container[self.second] = None
        self.assertEquals(len(container), 2)
