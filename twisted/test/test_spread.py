
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for twisted.spread package
"""

from zope.interface import implements
from twisted.trial import unittest

from twisted.spread.util import LocalAsyncForwarder
from twisted.internet import defer
from twisted.python.components import Interface

class IForwarded(Interface):
    def forwardMe(self):
        pass
    def forwardDeferred(self):
        pass

class Forwarded:

    implements(IForwarded)
    forwarded = 0
    unforwarded = 0

    def forwardMe(self):
        self.forwarded = 1

    def dontForwardMe(self):
        self.unforwarded = 1
    
    def forwardDeferred(self):
        return defer.succeed(1)

class SpreadUtilTest(unittest.TestCase):
    def testLocalAsyncForwarder(self):
        f = Forwarded()
        lf = LocalAsyncForwarder(f, IForwarded)
        lf.callRemote("forwardMe")
        assert f.forwarded
        lf.callRemote("dontForwardMe")
        assert not f.unforwarded
        rr = lf.callRemote("forwardDeferred")        
        l = []
        rr.addCallback(l.append)
        self.assertEqual(l[0], 1)
