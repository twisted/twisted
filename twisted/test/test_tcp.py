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
from twisted.internet import error


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



class MyServerFactory(protocol.ServerFactory):

    def buildProtocol(self, addr):
        p = MyProtocol()
        self.protocol = p
        return p


class MyClientFactory(protocol.ClientFactory):

    failed = 0
    
    def buildProtocol(self, addr):
        p = MyProtocol()
        self.protocol = p
        return p

    def connectionFailed(self, connector, reason):
        self.failed = 1
        self.reason = reason


class LoopbackTestCase(unittest.TestCase):
    """Test loopback connections."""
    
    def testClosePortInProtocolFactory(self):
        f = ClosingFactory()
        port = reactor.listenTCP(10080, f)
        f.port = port
        clientF = MyClientFactory()
        try:
            reactor.connectTCP("localhost", 10080, clientF)
        except:
            port.stopListening()
            raise


        while not clientF.protocol or not clientF.protocol.closed:
            reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        
        self.assert_(clientF.protocol.made)
        self.assert_(port.disconnected)

    def testTcpNoDelay(self):
        f = MyServerFactory()
        port = reactor.listenTCP(10080, f)
        clientF = MyClientFactory()
        try:
            reactor.connectTCP("localhost", 10080, clientF)
        except:
            port.stopListening()
            raise

        reactor.iterate()
        reactor.iterate()
        for p in clientF.protocol, f.protocol:
            transport = p.transport
            self.assertEquals(transport.getTcpNoDelay(), 0)
            transport.setTcpNoDelay(1)
            self.assertEquals(transport.getTcpNoDelay(), 1)
            transport.setTcpNoDelay(0)
            reactor.iterate()
            self.assertEquals(transport.getTcpNoDelay(), 0)

        clientF.protocol.transport.loseConnection()
        port.stopListening()
        reactor.iterate()
        reactor.iterate()
    
    def testFailing(self):
        clientF = MyClientFactory()
        reactor.connectTCP("localhost", 10081, clientF, timeout=5)

        while not clientF.failed:
            reactor.iterate()

        clientF.reason.trap(error.ConnectionRefusedError)


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


class ClientStartStopFactory(MyClientFactory):

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

    def testServerStartStop(self):
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

    def testClientStartStop(self):
        f = ClosingFactory()
        p = reactor.listenTCP(9995, f, interface="127.0.0.1")
        f.port = p
        reactor.iterate()
        reactor.iterate()

        factory = ClientStartStopFactory()
        reactor.connectTCP("127.0.0.1", 9995, factory)

        while not factory.stopped:
            reactor.iterate()


class CannotBindTestCase (unittest.TestCase):
    """Tests for correct behavior when a reactor cannot bind to the required TCP port."""

    def testCannotBind(self):
        f = MyServerFactory()

        # listen on port 9990
        p1 = reactor.listenTCP(9990, f, interface='127.0.0.1')
        self.assertEquals(p1.getHost(), ("INET", "127.0.0.1", 9990,))
        
        # make sure new listen raises error
        self.assertRaises(error.CannotListenError, reactor.listenTCP, 9990, f, interface='127.0.0.1')

        p1.stopListening()



