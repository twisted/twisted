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

from __future__ import nested_scopes

"""Generic TCP tests."""

import socket, time
from twisted.trial import unittest

from twisted.internet import protocol, reactor, defer
from twisted.internet import error
from twisted.internet.address import IPv4Address


class ClosingProtocol(protocol.Protocol):

    def connectionMade(self):
        self.transport.loseConnection()

    def connectionLost(self, reason):
        reason.trap(error.ConnectionDone)

class ClosingFactory(protocol.ServerFactory):
    """Factory that closes port immediatley."""
    
    def buildProtocol(self, conn):
        self.port.loseConnection()
        return ClosingProtocol()


class MyProtocol(protocol.Protocol):

    made = 0
    closed = 0
    failed = 0

    def connectionMade(self):
        self.made = 1
        
    def connectionLost(self, reason):
        self.closed = 1


class MyServerFactory(protocol.ServerFactory):

    called = 0

    def buildProtocol(self, addr):
        self.called += 1
        p = MyProtocol()
        self.protocol = p
        return p


class MyClientFactory(protocol.ClientFactory):

    failed = 0
    stopped = 0
    
    def buildProtocol(self, addr):
        p = MyProtocol()
        self.protocol = p
        return p

    def clientConnectionFailed(self, connector, reason):
        self.failed = 1
        self.reason = reason

    def clientConnectionLost(self, connector, reason):
        self.lostReason = reason

    def stopFactory(self):
        self.stopped = 1

class PortCleanerUpper(unittest.TestCase):
    def __init__(self):
        self.ports = []
    def tearDown(self):
        for p in self.ports:
            try:
                if self.connected:
                    p.stopListening()
            except:
                pass
        reactor.iterate()

class ListeningTestCase(PortCleanerUpper):

    def testListen(self):
        f = MyServerFactory()
        p1 = reactor.listenTCP(0, f, interface="127.0.0.1") 
        p1.stopListening()

    def testStopListening(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = port.getHost().port
        self.ports.append(port)
        l = []
        defer.maybeDeferred(port.stopListening).addCallback(l.append)
        while not l:
            reactor.iterate(0.1)
        port = reactor.listenTCP(n, f, interface="127.0.0.1")
        self.ports.append(port)

    def testNumberedInterface(self):
        f = MyServerFactory()
        # listen only on the loopback interface
        p1 = reactor.listenTCP(0, f, interface='127.0.0.1')
        p1.stopListening()
        
    def testNamedInterface(self):
        f = MyServerFactory()
        # use named interface instead of 127.0.0.1
        p1 = reactor.listenTCP(0, f, interface='localhost')
        # might raise exception if reactor can't handle named interfaces
        p1.stopListening()

class LoopbackTestCase(PortCleanerUpper):
    """Test loopback connections."""
        
    n = 10081

    def testClosePortInProtocolFactory(self):
        f = ClosingFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = port.getHost().port
        self.ports.append(port)
        f.port = port
        clientF = MyClientFactory()
        reactor.connectTCP("localhost", self.n, clientF)


        while not clientF.protocol or not clientF.protocol.closed:
            reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        
        self.assert_(clientF.protocol.made)
        self.assert_(port.disconnected)
        clientF.lostReason.trap(error.ConnectionDone)

    def testTcpNoDelay(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = port.getHost().port
        self.ports.append(port)
        clientF = MyClientFactory()
        reactor.connectTCP("localhost", self.n, clientF)

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
        clientF.lostReason.trap(error.ConnectionDone)

    def testTcpKeepAlive(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = port.getHost().port
        self.ports.append(port)
        clientF = MyClientFactory()
        reactor.connectTCP("localhost", self.n, clientF)

        reactor.iterate()
        reactor.iterate()
        for p in clientF.protocol, f.protocol:
            transport = p.transport
            self.assertEquals(transport.getTcpKeepAlive(), 0)
            transport.setTcpKeepAlive(1)
            self.assertEquals(transport.getTcpKeepAlive(), 1)
            transport.setTcpKeepAlive(0)
            reactor.iterate()
            self.assertEquals(transport.getTcpKeepAlive(), 0)

        clientF.protocol.transport.loseConnection()
        port.stopListening()
        reactor.iterate()
        reactor.iterate()
        clientF.lostReason.trap(error.ConnectionDone)
    
    def testFailing(self):
        clientF = MyClientFactory()
        # XXX we assume no one is listening on TCP port 69
        reactor.connectTCP("localhost", 69, clientF, timeout=5)
        start = time.time()
        
        while not clientF.failed:
            reactor.iterate()

        clientF.reason.trap(error.ConnectionRefusedError)
        #self.assert_(time.time() - start < 0.1)
    
    def testConnectByService(self):
        serv = socket.getservbyname
        s = MyServerFactory()
        port = reactor.listenTCP(0, s, interface="127.0.0.1")
        self.n = port.getHost().port
        socket.getservbyname = lambda s, p,n=self.n: s == 'http' and p == 'tcp' and n or 10
        self.ports.append(port)
        try:
            c = reactor.connectTCP('localhost', 'http', MyClientFactory())
        except:
            socket.getservbyname = serv
            raise
        
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        
        port.stopListening()
        c.disconnect()
        socket.getservbyname = serv
        assert s.called


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



class FactoryTestCase(PortCleanerUpper):
    """Tests for factories."""

    def testServerStartStop(self):
        f = StartStopFactory()

        # listen on port
        p1 = reactor.listenTCP(0, f, interface='127.0.0.1')
        self.n1 = p1.getHost().port
        self.ports.append(p1)
        reactor.iterate()
        reactor.iterate()
        self.assertEquals((f.started, f.stopped), (1, 0))
        
        # listen on two more ports
        p2 = reactor.listenTCP(0, f, interface='127.0.0.1')
        self.n2 = p2.getHost().port
        self.ports.append(p2)
        p3 = reactor.listenTCP(0, f, interface='127.0.0.1')
        self.n3 = p3.getHost().port
        self.ports.append(p3)
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
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = p.getHost().port
        self.ports.append(p)
        f.port = p
        reactor.iterate()
        reactor.iterate()

        factory = ClientStartStopFactory()
        reactor.connectTCP("127.0.0.1", self.n, factory)
        self.assert_(factory.started)
        reactor.iterate()
        reactor.iterate()
        
        while not factory.stopped:
            reactor.iterate()


class ConnectorTestCase(PortCleanerUpper):

    def testConnectorIdentity(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        f.port = p
        reactor.iterate()
        reactor.iterate()

        l = []; m = []
        factory = ClientStartStopFactory()
        factory.clientConnectionLost = lambda c, r: (l.append(c), m.append(r))
        factory.startedConnecting = lambda c: l.append(c)
        connector = reactor.connectTCP("127.0.0.1", n, factory)
        self.assertEquals(connector.getDestination(), ('INET', "127.0.0.1", n))
        
        i = 0
        while i < 50 and not factory.stopped:
            reactor.iterate(0.1)
            i += 1
        m[0].trap(error.ConnectionDone)
        self.assertEquals(l, [connector, connector])

    def testUserFail(self):
        f = MyServerFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        
        def startedConnecting(connector):
            connector.stopConnecting()

        factory = ClientStartStopFactory()
        factory.startedConnecting = startedConnecting
        reactor.connectTCP("127.0.0.1", n, factory)

        while not factory.stopped:
            reactor.iterate()

        self.assertEquals(factory.failed, 1)
        factory.reason.trap(error.UserError)

        p.stopListening()
        reactor.iterate()


    def testReconnect(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        f.port = p
        reactor.iterate()
        reactor.iterate()

        factory = MyClientFactory()
        def clientConnectionLost(c, reason):
            c.connect()
        factory.clientConnectionLost = clientConnectionLost
        reactor.connectTCP("127.0.0.1", n, factory)
        
        i = 0
        while i < 50 and not factory.failed:
            reactor.iterate(0.1)
            i += 1

        p = factory.protocol
        self.assertEquals((p.made, p.closed), (1, 1))
        factory.reason.trap(error.ConnectionRefusedError)
        self.assertEquals(factory.stopped, 1)


class CannotBindTestCase(PortCleanerUpper):
    """Tests for correct behavior when a reactor cannot bind to the required TCP port."""

    def testCannotBind(self):
        f = MyServerFactory()

        p1 = reactor.listenTCP(0, f, interface='127.0.0.1')
        n = p1.getHost().port
        self.ports.append(p1)
        self.assertEquals(p1.getHost(), ("INET", "127.0.0.1", n,))
        
        # make sure new listen raises error
        self.assertRaises(error.CannotListenError, reactor.listenTCP, n, f, interface='127.0.0.1')

        p1.stopListening()

    def testClientBind(self):
        f = MyServerFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.ports.append(p)
        
        factory = MyClientFactory()
        reactor.connectTCP("127.0.0.1", p.getHost().port, factory, bindAddress=("127.0.0.1", 0))
        while not factory.protocol:
            reactor.iterate()
        
        self.assertEquals(factory.protocol.made, 1)

        port = factory.protocol.transport.getHost().port
        f2 = MyClientFactory()
        reactor.connectTCP("127.0.0.1", p.getHost().port, f2, bindAddress=("127.0.0.1", port))
        reactor.iterate()
        reactor.iterate()
        
        self.assertEquals(f2.failed, 1)
        f2.reason.trap(error.ConnectBindError)
        self.assertEquals(f2.stopped, 1)
        
        p.stopListening()
        factory.protocol.transport.loseConnection()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(factory.stopped, 1)

class MyOtherClientFactory(protocol.ClientFactory):
    def buildProtocol(self, address):
        self.address = address
        self.protocol = MyProtocol()
        return self.protocol


class LocalRemoteAddressTestCase(PortCleanerUpper):
    """Tests for correct getHost/getPeer values and that the correct address
    is passed to buildProtocol.
    """
    def testHostAddress(self):
        f1 = MyServerFactory()
        p1 = reactor.listenTCP(0, f1, interface='127.0.0.1')
        n = p1.getHost().port
        self.ports.append(p1)
        
        f2 = MyOtherClientFactory()
        p2 = reactor.connectTCP('127.0.0.1', n, f2)

        for i in range(5):
            reactor.iterate(0.01)

        self.assertEquals(p1.getHost(), f2.address)
        self.assertEquals(p1.getHost(), f2.protocol.transport.getPeer())

        p1.stopListening()
        p2.disconnect()
    

class WriterProtocol(protocol.Protocol):
    def connectionMade(self):
        # use everything ITransport claims to provide. If something here
        # fails, the exception will be written to the log, but it will not
        # directly flunk the test. The test will fail when maximum number of
        # iterations have passed and the writer's factory.done has not yet
        # been set.
        self.transport.write("Hello Cleveland!\n")
        seq = ["Goodbye", " cruel", " world", "\n"]
        self.transport.writeSequence(seq)
        peer = self.transport.getPeer()
        if peer[0] != "INET":
            print "getPeer returned non-INET socket:", peer
            self.factory.problem = 1
        us = self.transport.getHost()
        if us[0] != "INET":
            print "getHost returned non-INET socket:", us
            self.factory.problem = 1
        self.factory.done = 1
        
        self.transport.loseConnection()

class ReaderProtocol(protocol.Protocol):
    def dataReceived(self, data):
        self.factory.data += data
    def connectionLost(self, reason):
        self.factory.done = 1

class WriterClientFactory(protocol.ClientFactory):
    def __init__(self):
        self.done = 0
        self.data = ""
    def buildProtocol(self, addr):
        p = ReaderProtocol()
        p.factory = self
        self.protocol = p
        return p
    
class WriteDataTestCase(PortCleanerUpper):
    """Test that connected TCP sockets can actually write data. Try to
    exercise the entire ITransport interface.
    """
            
    def testWriter(self):
        f = protocol.Factory()
        f.protocol = WriterProtocol
        f.done = 0
        f.problem = 0
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        clientF = WriterClientFactory()
        reactor.connectTCP("localhost", n, clientF)
        count = 0
        while not ((count > 20) or (f.done and clientF.done)):
            reactor.iterate()
            count += 1
        self.failUnless(f.done, "writer didn't finish, it probably died")
        self.failUnless(f.problem == 0, "writer indicated an error")
        self.failUnless(clientF.done, "client didn't see connection dropped")
        expected = "".join(["Hello Cleveland!\n",
                            "Goodbye", " cruel", " world", "\n"])
        self.failUnless(clientF.data == expected,
                        "client didn't receive all the data it expected")
        p.stopListening()

class ConnectionLosingProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.write("1")
        self.transport.loseConnection()
        self.master._connectionMade()

class ProperlyCloseFilesTestCase(unittest.TestCase):

    numberRounds = 2048
    timeLimit = 200
    
    def setUp(self):
        f = protocol.ServerFactory()
        f.protocol = protocol.Protocol
        self.listener = reactor.listenTCP(0, f, interface="127.0.0.1")
        
        f = protocol.ClientFactory()
        f.protocol = ConnectionLosingProtocol
        f.protocol.master = self
        
        def connector():
            p = self.listener.getHost().port
            return reactor.connectTCP('127.0.0.1', p, f)
        self.connector = connector

        self.totalConnections = 0
    
    def testProperlyCloseFiles(self):
        self.connector()
        timeLimit = time.time() + self.timeLimit
        while (self.totalConnections < self.numberRounds and 
               time.time() < timeLimit):
            reactor.iterate(0.01)
        reactor.iterate(0.01)

        self.failUnlessEqual(self.totalConnections, self.numberRounds)

    def _connectionMade(self):
        self.totalConnections += 1
        if self.totalConnections<self.numberRounds:
            self.connector()

    def tearDown(self):
        self.listener.stopListening()


class AProtocol(protocol.Protocol):

    def connectionMade(self):
        reactor.callLater(0.1, self.transport.loseConnection)
        self.factory.testcase.assertEquals(self.transport.getHost(),
                          IPv4Address("TCP", self.transport.getHost().host, self.transport.getHost().port))
        self.factory.testcase.assertEquals(self.transport.getPeer(),
                          IPv4Address("TCP", self.transport.getPeer().host, self.transport.getPeer().port))
        self.factory.testcase.assertEquals(self.transport.getPeer(), self.factory.ipv4addr)
        self.factory.testcase.ran = 1

class AClientFactory(protocol.ClientFactory):

    def __init__(self, testcase, ipv4addr):
        self.testcase = testcase
        self.ipv4addr = ipv4addr

    def buildProtocol(self, addr):
        self.testcase.assertEquals(addr, self.ipv4addr)
        self.testcase.assertEquals(addr, ('INET', self.ipv4addr.host, self.ipv4addr.port))
        p = AProtocol()
        p.factory = self
        return p
        
class AServerFactory(protocol.ServerFactory):

    def __init__(self, testcase, ipv4addr):
        self.testcase = testcase
        self.ipv4addr = ipv4addr
    
    def buildProtocol(self, addr):
        self.testcase.assertEquals(addr, self.ipv4addr)
        self.testcase.assertEquals(addr, (self.ipv4addr.host, self.ipv4addr.port))
        p = AProtocol()
        p.factory = self
        return p

class AddressTestCase(unittest.TestCase):

    def getFreePort(self):
        """Get an empty port."""
        p = reactor.listenTCP(0, protocol.ServerFactory())
        reactor.iterate(); reactor.iterate()
        port = p.getHost().port
        p.stopListening()
        reactor.iterate(); reactor.iterate()
        return port
    
    def testBuildProtocol(self):
        portno = self.getFreePort()
        p = reactor.listenTCP(0, AServerFactory(self, IPv4Address('TCP', '127.0.0.1', portno)))
        reactor.iterate()
        reactor.connectTCP("127.0.0.1", p.getHost().port,
                           AClientFactory(self, IPv4Address("TCP", "127.0.0.1", p.getHost().port)),
                           bindAddress=("127.0.0.1", portno))
        self.runReactor(0.4, True)
        p.stopListening()
        self.assert_(hasattr(self, "ran"))
        del self.ran


try:
    import resource
except ImportError:
    pass
else:
    ProperlyCloseFilesTestCase.numberRounds = resource.getrlimit(resource.RLIMIT_NOFILE)[0] + 10
