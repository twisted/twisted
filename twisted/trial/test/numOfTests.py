# -*- test-case-name: twisted.trial.test.test_trial -*-
from twisted.trial import unittest

class NumberOfTests(unittest.TestCase):
    testNames = 'foo'
    def testFoo(self):
        pass

