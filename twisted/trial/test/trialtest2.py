
"""
as trial now supports PyUnit-tests, we should see if we can run them and find them

"""

import unittest

from twisted.trial.test.trialtest1 import BaseTest

class PyUnitTest(BaseTest, unittest.TestCase):
    pass

