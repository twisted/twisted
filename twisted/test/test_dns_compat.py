import os, string, shutil

from twisted.trial import unittest

goodnames = False
try:
    from twisted.protocols import dns as bcdns
    from twisted.names import dns
except ImportError, e:
    goodnames = e


class TestCompatibility(unittest.TestCase):
    def testCompatibility(self):
        self.assertIdentical(dns.Record_A, bcdns.Record_A)
        
if goodnames:
    TestCompatibility.skip = "Couldn't find twisted.names package. %s" % goodnames

