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

class MyProtocol(protocol.Protocol):

    made = 0
    closed = 0
    failed = 0

    def connectionMade(self):
        self.made = 1
        
    def connectionLost(self):
        self.closed = 1

    def connectionFailed(self):
        self.failed = 1

class MyFactory(protocol.ServerFactory):

    def buildProtocol(self, addr):
        p = MyProtocol()
        self.protocol = p
        return p


class LoopbackTestCase(unittest.TestCase):
    """Test loopback connections."""
    
    def testClosePortInProtocolFactory(self):
        f = ClosingFactory()
        port = reactor.listenTCP(10080, f)
        f.port = port
        client = MyProtocol()
        try:
            reactor.clientTCP("localhost", 10080, client)
        except:
            port.stopListening()
            raise
        
        while not client.closed:
            reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        
        self.assert_(client.made)
        self.assert_(port.disconnected)

    def testTcpNoDelay(self):
        f = MyFactory()
        port = reactor.listenTCP(10080, f)
        client = MyProtocol()
        try:
            reactor.clientTCP("localhost", 10080, client)
        except:
            port.stopListening()
            raise

        reactor.iterate()
        reactor.iterate()
        for p in client, f.protocol:
            transport = p.transport
            self.assertEquals(transport.getTcpNoDelay(), 0)
            transport.setTcpNoDelay(1)
            self.assertEquals(transport.getTcpNoDelay(), 1)
            transport.setTcpNoDelay(0)
            reactor.iterate()
            self.assertEquals(transport.getTcpNoDelay(), 0)

        client.transport.loseConnection()
        port.stopListening()
        reactor.iterate()
        reactor.iterate()
    
    def testFailing(self):
        client = MyProtocol()
        reactor.clientTCP("localhost", 10081, client, timeout=5)

        while not client.failed:
            reactor.iterate()
            if client.closed:
                raise ValueError, "connectionLost called instead of connectionFailed"
        self.assert_(not client.made)


class StartStopFactory(protocol.Factory):

    started = 0
    stopped = 0
    
    def startFactory(self):
        if self.started or self.stopped:
            raise RuntimeError
        self.started = 1

    def stopFactory(self):
        if not self.started or self.stopped:
            raise RuntimeError
        self.stopped = 1


class FactoryTestCase(unittest.TestCase):
    """Tests for factories."""

    def testStartStop(self):
        f = StartStopFactory()

        # listen on port
        p1 = reactor.listenTCP(9995, f, interface='127.0.0.1')
        reactor.iterate()
        reactor.iterate()
        self.assertEquals((f.started, f.stopped), (1, 0))
        
        # listen on two more ports
        p2 = reactor.listenTCP(9996, f, interface='127.0.0.1')
        p3 = reactor.listenTCP(9997, f, interface='127.0.0.1')
        reactor.iterate()
        reactor.iterate()
        self.assertEquals((f.started, f.stopped), (1, 0))

        # close two ports
        p1.stopListening()
        p2.stopListening()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals((f.started, f.stopped), (1, 0))

        # close last port
        p3.stopListening()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals((f.started, f.stopped), (1, 1))
