
"""
as trial now supports PyUnit-tests, we should see if we can run them and find them

"""

import unittest

SET_UP_MSG = "ran setUp"
SET_UP_CLASS_MSG = "ran setUpClass"
TEAR_DOWN_MSG = "ran tearDown"
TEAR_DOWN_CLASS_MSG = "ran tearDownClass"
RAN_METHOD = "ran method"

MESSAGES = [SET_UP_CLASS_MSG, SET_UP_MSG, TEAR_DOWN_CLASS_MSG, TEAR_DOWN_MSG, RAN_METHOD]

class TestPyUnitSupport(unittest.TestCase):
    def setUpClass(self):
        print SET_UP_CLASS_MSG

    def setUp(self):
        print SET_UP_MSG

    def tearDown(self):
        print TEAR_DOWN_MSG

    def tearDownClass(self):
        print TEAR_DOWN_CLASS_MSG

    def testFoobar(self):
        print RAN_METHOD
