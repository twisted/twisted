
"""
Test cases for dirdbm module.
"""

from pyunit import unittest
from twisted.persisted import dirdbm
import os

class DirDbmTestCase(unittest.TestCase):

    def setUp(self):
        self.dbm = dirdbm.open("/tmp/dirdbm")

    def tearDown(self):
        os.rmdir("/tmp/dirdbm")

    def testDbm(self):
        self.dbm['hello'] = 'world'
        if self.dbm['hello'] != 'world':
            raise AssertionError(self.dbm['hello'])
        if not self.dbm.has_key('hello'):
            raise AssertionError
        if self.dbm.has_key('goodbye'):
            raise AssertionError
        del self.dbm['hello']

testCases = [DirDbmTestCase]
