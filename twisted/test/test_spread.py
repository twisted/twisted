
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Test cases for twisted.spread package
"""

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

    __implements__ = IForwarded
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
