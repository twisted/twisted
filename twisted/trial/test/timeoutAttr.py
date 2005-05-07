# -*- test-case-name: twisted.trial.test.test_trial -*-

"""
test to make sure that timeout attribute 'sticks' at the class level
"""

from twisted.trial import unittest
from twisted.trial.test import common
from twisted.internet import defer

class TestClassTimeoutAttribute(common.BaseTest, unittest.TestCase):
    def setUp(self):
        self.d = defer.Deferred()

    def testMethod(self):
        self.methodCalled = True
        return self.d

TestClassTimeoutAttribute.timeout = 0.2
