# -*- test-case-name: twisted.trial.test.test_trial -*-

"""
as trial now supports PyUnit-tests, we should see if we can run them and find them

"""

import unittest

from twisted.trial.test.common import BaseTest

class PyUnitTest(BaseTest, unittest.TestCase):
    pass

