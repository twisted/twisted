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

"""Generic TCP tests."""

from pyunit import unittest

from twisted.internet import protocol, reactor


class ClosingFactory(protocol.ServerFactory):
    """Factory that closes port immediatley."""
    
    def buildProtocol(self, conn):
        self.port.loseConnection()
        return

class ClosingProtocol(protocol.Protocol):

    made = 0
    closed = 0
    failed = 0

    def connectionMade(self):
        self.made = 1
        
    def connectionLost(self):
        self.closed = 1

    def connectionFailed(self):
        self.failed = 1


class LoopbackTestCase(unittest.TestCase):
    """Test loopback connections."""
    
    def testClosePortInProtocolFactory(self):
        f = ClosingFactory()
        port = reactor.listenTCP(10080, f)
        f.port = port
        client = ClosingProtocol()
        reactor.clientTCP("localhost", 10080, client)
        
        while not client.closed:
            reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        
        self.assert_(client.made)
        self.assert_(port.disconnected)

    def testFailing(self):
        client = ClosingProtocol()
        reactor.clientTCP("localhost", 10081, client, timeout=5)

        while not client.failed:
            reactor.iterate()
            if client.closed:
                raise ValueError, "connectionLost called instead of connectionFailed"
        self.assert_(not client.made)
