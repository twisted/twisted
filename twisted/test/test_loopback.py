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
Test case for twisted.protocols.loopback
"""

from __future__ import nested_scopes

from twisted.trial import unittest
from twisted.protocols import basic, loopback
from twisted.internet import defer

class SimpleProtocol(basic.LineReceiver):
    connLost = None

    def __init__(self):
        self.conn = defer.Deferred()
        self.lines = []

    def connectionMade(self):
        self.conn.callback(None)
    
    def lineReceived(self, line):
        self.lines.append(line)
    
    def connectionLost(self, reason):
        self.connLost = 1

class DoomProtocol(SimpleProtocol):
    i = 0
    def lineReceived(self, line):
        self.i += 1
        if self.i < 4:
            # by this point we should have connection closed,
            # but just in case we didn't we won't ever send 'Hello 4'
            self.sendLine("Hello %d" % self.i)
        SimpleProtocol.lineReceived(self, line)
        if self.lines[-1] == "Hello 3":
            self.transport.loseConnection()


class LoopbackTestCase(unittest.TestCase):
    loopbackFunc = loopback.loopback
    def testRegularFunction(self):
        s = SimpleProtocol()
        c = SimpleProtocol()
        
        def sendALine(result):
            s.sendLine("THIS IS LINE ONE!")
            s.transport.loseConnection()
        s.conn.addCallback(sendALine)

        self.loopbackFunc.im_func(s, c)
        self.assertEquals(c.lines, ["THIS IS LINE ONE!"])
        self.assertEquals(s.connLost, 1)
        self.assertEquals(c.connLost, 1)
    
    def testSneakyHiddenDoom(self):
        s = DoomProtocol()
        c = DoomProtocol()
        
        def sendALine(result):
            s.sendLine("DOOM LINE")
        s.conn.addCallback(sendALine)
        
        self.loopbackFunc.im_func(s, c)
        self.assertEquals(s.lines, ['Hello 1', 'Hello 2', 'Hello 3'])
        self.assertEquals(c.lines, ['DOOM LINE', 'Hello 1', 'Hello 2', 'Hello 3'])
        self.assertEquals(s.connLost, 1)
        self.assertEquals(c.connLost, 1)

class LoopbackTCPTestCase(LoopbackTestCase):
    loopbackFunc = loopback.loopbackTCP


