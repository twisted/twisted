import os, string, shutil

from twisted.trial import unittest

goodnews = False
try:
    from twisted.protocols import nntp as bcnntp
    from twisted.news import nntp
except ImportError, e:
    goodnews = e


class TestCompatibility(unittest.TestCase):
    def testCompatibility(self):
        self.assertIdentical(nntp.NNTPServer, bcnntp.NNTPServer)
        
if goodnews:
    TestCompatibility.skip = "Couldn't find twisted.news package. %s" % goodnews

