
from twisted.trial import unittest

from twisted.spread.util import LocalAsyncForwarder
from twisted.python.components import Interface

class IForwarded:
    def forwardMe(self):
        pass

class Forwarded:

    __implements__ = IForwarded
    forwarded = 0
    unforwarded = 0

    def forwardMe(self):
        self.forwarded = 1

    def dontForwardMe(self):
        self.unforwarded = 1

        

class SpreadUtilTest(unittest.TestCase):
    def testLocalAsyncForwarder(self):
        f = Forwarded()
        lf = LocalAsyncForwarder(f, IForwarded)
        lf.callRemote("forwardMe")
        assert f.forwarded
        lf.callRemote("dontForwardMe")
        assert not f.unforwarded
