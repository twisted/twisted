# -*- test-case-name: twisted.test.test_tcp -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from __future__ import nested_scopes

"""Generic TCP tests."""

import socket, time, os
from zope.interface import implements
from twisted.trial import unittest, util
from twisted.trial.util import spinWhile, spinUntil
from  twisted.python import log

from twisted.internet import protocol, reactor, defer, interfaces
from twisted.internet import error
from twisted.internet.address import IPv4Address
from twisted.internet.interfaces import IHalfCloseableProtocol

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
    made = closed = failed = 0
    data = ""
    def connectionMade(self):
        self.made = 1

    def dataReceived(self, data):
        self.data += data

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

    def clientConnectionFailed(self, connector, reason):
        self.failed = 1
        self.reason = reason

    def clientConnectionLost(self, connector, reason):
        self.lostReason = reason

    def stopFactory(self):
        self.stopped = 1

    def buildProtocol(self, addr):
        p = MyProtocol()
        self.protocol = p
        return p



class PortCleanerUpper(unittest.TestCase):
    def setUp(self):
        self.ports = []

    def tearDown(self):
        self.cleanPorts(*self.ports)

    def cleanPorts(self, *ports):
        for p in ports:
            if p.connected:
                p.loseConnection()
                util.spinWhile(lambda :p.connected)



class ListeningTestCase(PortCleanerUpper):

    def testListen(self):
        f = MyServerFactory()
        p1 = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.failUnless(interfaces.IListeningPort.providedBy(p1))
        p1.stopListening()

    def testStopListening(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = port.getHost().port
        self.ports.append(port)

        def cbStopListening(ignored):
            # Make sure we can rebind the port right away
            port = reactor.listenTCP(n, f, interface="127.0.0.1")
            self.ports.append(port)

        d = defer.maybeDeferred(port.stopListening)
        d.addCallback(cbStopListening)
        return d

    def testNumberedInterface(self):
        f = MyServerFactory()
        # listen only on the loopback interface
        p1 = reactor.listenTCP(0, f, interface='127.0.0.1')
        p1.stopListening()

    def testPortRepr(self):
        f = MyServerFactory()
        p = reactor.listenTCP(0, f)
        portNo = str(p.getHost().port)
        self.failIf(repr(p).find(portNo) == -1)
        def stoppedListening(ign):
            self.failIf(repr(p).find(portNo) != -1)
        return defer.maybeDeferred(p.stopListening).addCallback(stoppedListening)


def callWithSpew(f):
    from twisted.python.util import spewerWithLinenums as spewer
    import sys
    sys.settrace(spewer)
    try:
        f()
    finally:
        sys.settrace(None)

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
        reactor.connectTCP("127.0.0.1", self.n, clientF)

        spinWhile(lambda :(not clientF.protocol or
                           not clientF.protocol.closed))

        self.assert_(clientF.protocol.made)
        self.assert_(port.disconnected)
        clientF.lostReason.trap(error.ConnectionDone)

    def _trapCnxDone(self, obj):
        getattr(obj, 'trap', lambda x: None)(error.ConnectionDone)

    def testTcpNoDelay(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")

        self.n = port.getHost().port
        self.ports.append(port)
        clientF = MyClientFactory()
        reactor.connectTCP("127.0.0.1", self.n, clientF)

        spinUntil(lambda :(f.called > 0 and
                           getattr(clientF, 'protocol', None) is not None))

        for p in clientF.protocol, f.protocol:
            transport = p.transport
            self.assertEquals(transport.getTcpNoDelay(), 0)
            transport.setTcpNoDelay(1)
            self.assertEquals(transport.getTcpNoDelay(), 1)
            transport.setTcpNoDelay(0)
            reactor.iterate()
            self.assertEquals(transport.getTcpNoDelay(), 0)

        self.cleanPorts(clientF.protocol.transport, port)

        clientF.lostReason.trap(error.ConnectionDone)

    def testTcpKeepAlive(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = port.getHost().port
        self.ports.append(port)
        clientF = MyClientFactory()
        reactor.connectTCP("127.0.0.1", self.n, clientF)

        spinUntil(lambda :(f.called > 0 and
                           getattr(clientF, 'protocol', None) is not None))

        for p in clientF.protocol, f.protocol:
            transport = p.transport
            self.assertEquals(transport.getTcpKeepAlive(), 0)
            transport.setTcpKeepAlive(1)
            self.assertEquals(transport.getTcpKeepAlive(), 1)
            transport.setTcpKeepAlive(0)

            spinUntil(lambda :transport.getTcpKeepAlive() == 0, timeout=1.0)

        self.cleanPorts(clientF.protocol.transport, port)
        clientF.lostReason.trap(error.ConnectionDone)

    def testFailing(self):
        clientF = MyClientFactory()
        # XXX we assume no one is listening on TCP port 69
        reactor.connectTCP("127.0.0.1", 69, clientF, timeout=5)
        start = time.time()

        spinUntil(lambda :clientF.failed)

        clientF.reason.trap(error.ConnectionRefusedError)
        #self.assert_(time.time() - start < 0.1)

    def testConnectByServiceFail(self):
        try:
            reactor.connectTCP("127.0.0.1", "thisbetternotexist",
                               MyClientFactory())
        except error.ServiceNameUnknownError:
            return
        self.assert_(False, "connectTCP didn't raise ServiceNameUnknownError")
    
    def testConnectByService(self):
        serv = socket.getservbyname
        try:
            s = MyServerFactory()
            port = reactor.listenTCP(0, s, interface="127.0.0.1")
            self.n = port.getHost().port
            socket.getservbyname = (lambda s, p,n=self.n:
                                    s == 'http' and p == 'tcp' and n or 10)
            self.ports.append(port)
            cf = MyClientFactory()
            try:
                c = reactor.connectTCP('127.0.0.1', 'http', cf)
            except:
                socket.getservbyname = serv
                raise

            spinUntil(lambda :getattr(s, 'protocol', None) is not None)
            self.cleanPorts(port, c.transport, cf.protocol.transport)

        finally:
            socket.getservbyname = serv
        self.assert_(s.called, '%s was not called' % (s,))


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

        spinUntil(lambda :(p1.connected == 1))

        self.assertEquals((f.started, f.stopped), (1,0))

        # listen on two more ports
        p2 = reactor.listenTCP(0, f, interface='127.0.0.1')
        self.n2 = p2.getHost().port
        self.ports.append(p2)
        p3 = reactor.listenTCP(0, f, interface='127.0.0.1')
        self.n3 = p3.getHost().port
        self.ports.append(p3)

        spinUntil(lambda :(p2.connected == 1 and p3.connected == 1))

        self.assertEquals((f.started, f.stopped), (1, 0))

        # close two ports
        p1.stopListening()
        p2.stopListening()

        spinWhile(lambda :(p1.connected == 1 or p2.connected == 1))

        self.assertEquals((f.started, f.stopped), (1, 0))

        # close last port
        p3.stopListening()

        spinWhile(lambda :(p3.connected == 1))

        self.assertEquals((f.started, f.stopped), (1, 1))
        self.cleanPorts(*self.ports)


    def testClientStartStop(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = p.getHost().port
        self.ports.append(p)
        f.port = p

        spinUntil(lambda :p.connected)

        factory = ClientStartStopFactory()
        reactor.connectTCP("127.0.0.1", self.n, factory)
        self.assert_(factory.started)
        reactor.iterate()
        reactor.iterate()

        spinUntil(lambda :factory.stopped)

        self.cleanPorts(*self.ports)


class ConnectorTestCase(PortCleanerUpper):

    def testConnectorIdentity(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        f.port = p

        spinUntil(lambda :p.connected)

        l = []; m = []
        factory = ClientStartStopFactory()
        factory.clientConnectionLost = lambda c, r: (l.append(c), m.append(r))
        factory.startedConnecting = lambda c: l.append(c)
        connector = reactor.connectTCP("127.0.0.1", n, factory)
        self.failUnless(interfaces.IConnector.providedBy(connector))
        dest = connector.getDestination()
        self.assertEquals(dest.type, "TCP")
        self.assertEquals(dest.host, "127.0.0.1")
        self.assertEquals(dest.port, n)

        spinUntil(lambda :factory.stopped)

        self.cleanPorts(*self.ports)

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

        spinUntil(lambda :factory.stopped)

        self.assertEquals(factory.failed, 1)
        factory.reason.trap(error.UserError)

        self.cleanPorts(*self.ports)
        

    def testReconnect(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        f.port = p

        spinUntil(lambda :p.connected)

        factory = MyClientFactory()
        def clientConnectionLost(c, reason):
            c.connect()
        factory.clientConnectionLost = clientConnectionLost
        reactor.connectTCP("127.0.0.1", n, factory)
        
        spinUntil(lambda :factory.failed)

        p = factory.protocol
        self.assertEquals((p.made, p.closed), (1, 1))
        factory.reason.trap(error.ConnectionRefusedError)
        self.assertEquals(factory.stopped, 1)

        self.cleanPorts(*self.ports)


class CannotBindTestCase(PortCleanerUpper):
    """Tests for correct behavior when a reactor cannot bind to the required
    TCP port."""

    def testCannotBind(self):
        f = MyServerFactory()

        p1 = reactor.listenTCP(0, f, interface='127.0.0.1')
        n = p1.getHost().port
        self.ports.append(p1)
        dest = p1.getHost()
        self.assertEquals(dest.type, "TCP")
        self.assertEquals(dest.host, "127.0.0.1")
        self.assertEquals(dest.port, n)
        
        # make sure new listen raises error
        self.assertRaises(error.CannotListenError,
                          reactor.listenTCP, n, f, interface='127.0.0.1')

        self.cleanPorts(*self.ports)

    def testClientBind(self):
        f = MyServerFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.ports.append(p)
        
        factory = MyClientFactory()
        reactor.connectTCP("127.0.0.1", p.getHost().port, factory,
                           bindAddress=("127.0.0.1", 0))

        spinUntil(lambda :factory.protocol is not None)
        
        self.assertEquals(factory.protocol.made, 1)

        port = factory.protocol.transport.getHost().port
        f2 = MyClientFactory()
        reactor.connectTCP("127.0.0.1", p.getHost().port, f2,
                           bindAddress=("127.0.0.1", port))


        spinUntil(lambda :f2.failed)
        
        self.assertEquals(f2.failed, 1)
        f2.reason.trap(error.ConnectBindError)
        self.assert_(f2.reason.check(error.ConnectBindError))
        self.assertEquals(f2.stopped, 1)
        
        p.stopListening()
        factory.protocol.transport.loseConnection()

        spinWhile(lambda :p.connected)

        self.assertEquals(factory.stopped, 1)
        self.cleanPorts(*self.ports)

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

        spinUntil(lambda :p2.state == "connected")

        self.assertEquals(p1.getHost(), f2.address)
        self.assertEquals(p1.getHost(), f2.protocol.transport.getPeer())

        util.wait(defer.maybeDeferred(p1.stopListening))
        self.ports.append(p2.transport)
        self.cleanPorts(*self.ports)
        

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
        if peer.type != "TCP":
            print "getPeer returned non-TCP socket:", peer
            self.factory.problem = 1
        us = self.transport.getHost()
        if us.type != "TCP":
            print "getHost returned non-TCP socket:", us
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
        reactor.connectTCP("127.0.0.1", n, clientF)

        spinUntil(lambda :(f.done and clientF.done))

        self.failUnless(f.done, "writer didn't finish, it probably died")
        self.failUnless(f.problem == 0, "writer indicated an error")
        self.failUnless(clientF.done, "client didn't see connection dropped")
        expected = "".join(["Hello Cleveland!\n",
                            "Goodbye", " cruel", " world", "\n"])
        self.failUnless(clientF.data == expected,
                        "client didn't receive all the data it expected")


class ConnectionLosingProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.write("1")
        self.transport.loseConnection()
        self.master._connectionMade()
        self.master.ports.append(self.transport)

class NoopProtocol(protocol.Protocol):
    def connectionMade(self):
        self.d = defer.Deferred()
        self.master.serverConns.append(self.d)

    def connectionLost(self, reason):
        self.d.callback(True)

class ProperlyCloseFilesTestCase(PortCleanerUpper):

    numberRounds = 2048
    timeLimit = 200

    def _setUp(self):
        # This method is used by test_ssl
        PortCleanerUpper.setUp(self)
        self.serverConns = []

    def setUp(self):
        self._setUp()
        f = protocol.ServerFactory()
        f.protocol = NoopProtocol
        f.protocol.master = self

        self.listener = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.ports.append(self.listener)
        
        self.clientF = f = protocol.ClientFactory()
        f.protocol = ConnectionLosingProtocol
        f.protocol.master = self
        
        def connector():
            p = self.listener.getHost().port
            return reactor.connectTCP('127.0.0.1', p, f)
        self.connector = connector

        self.totalConnections = 0

    def tearDown(self):
        # Wait until all the protocols on the server-side of this test have
        # been disconnected, to avoid leaving junk in the reactor.
        for d in self.serverConns:
            util.wait(d)

        PortCleanerUpper.tearDown(self)
    
    def testProperlyCloseFiles(self):
        self.connector()
        
        f = lambda :(self.totalConnections < self.numberRounds)
        spinWhile(f, timeout=self.timeLimit)

        self.failUnlessEqual(self.totalConnections, self.numberRounds)

    def _connectionMade(self):
        self.totalConnections += 1
        if self.totalConnections<self.numberRounds:
            self.connector()



class AProtocol(protocol.Protocol):
    lostCnx = 0
    def connectionLost(self, reason):
        self.lostCnx = 1

    def connectionMade(self):
        reactor.callLater(0.1, self.transport.loseConnection)
        self.factory.testcase.assertEquals(self.transport.getHost(),
                          IPv4Address("TCP", self.transport.getHost().host,
                                      self.transport.getHost().port))
        self.factory.testcase.assertEquals(self.transport.getPeer(),
                          IPv4Address("TCP", self.transport.getPeer().host,
                                      self.transport.getPeer().port))
        self.factory.testcase.assertEquals(self.transport.getPeer(),
                                           self.factory.ipv4addr)
        self.factory.testcase.ran = 1

class AClientFactory(protocol.ClientFactory):
    protocol = None

    def __init__(self, testcase, ipv4addr):
        self.testcase = testcase
        self.ipv4addr = ipv4addr

    def buildProtocol(self, addr):
        self.testcase.assertEquals(addr, self.ipv4addr)
        self.testcase.assertEquals(addr.type, "TCP")
        self.testcase.assertEquals(addr.host, self.ipv4addr.host)
        self.testcase.assertEquals(addr.port, self.ipv4addr.port)
        self.protocol = p = AProtocol()
        p.factory = self
        return p
        
class AServerFactory(protocol.ServerFactory):
    protocol = None

    def __init__(self, testcase, ipv4addr):
        self.testcase = testcase
        self.ipv4addr = ipv4addr
    
    def buildProtocol(self, addr):
        self.testcase.assertEquals(addr, self.ipv4addr)
        self.testcase.assertEquals(addr.type, "TCP")
        self.testcase.assertEquals(addr.host, self.ipv4addr.host)
        self.testcase.assertEquals(addr.port, self.ipv4addr.port)
        self.protocol = p = AProtocol()
        p.factory = self
        return p

class AddressTestCase(PortCleanerUpper):

    def getFreePort(self):
        """Get an empty port."""
        p = reactor.listenTCP(0, protocol.ServerFactory())
        spinUntil(lambda :p.connected)
        port = p.getHost().port
        p.stopListening()
        spinWhile(lambda :p.connected)
        return port
    
    def testBuildProtocol(self):
        portno = self.getFreePort()

        f = AServerFactory(self, IPv4Address('TCP', '127.0.0.1', portno))
        p = reactor.listenTCP(0, f)
        self.ports.append(p)
        spinUntil(lambda :p.connected)

        acf = AClientFactory(self, IPv4Address("TCP", "127.0.0.1",
                                               p.getHost().port))

        reactor.connectTCP("127.0.0.1", p.getHost().port, acf,
                           bindAddress=("127.0.0.1", portno))

        spinUntil(lambda :acf.protocol is not None)
        self.ports.append(acf.protocol.transport)

        self.assert_(hasattr(self, "ran"))
        spinUntil(lambda :acf.protocol.lostCnx)
        del self.ran


class LargeBufferWriterProtocol(protocol.Protocol):

    # Win32 sockets cannot handle single huge chunks of bytes.  Write one
    # massive string to make sure Twisted deals with this fact.

    def connectionMade(self):
        # write 60MB
        self.transport.write('X'*self.factory.len)
        self.factory.done = 1
        self.transport.loseConnection()

class LargeBufferReaderProtocol(protocol.Protocol):
    def dataReceived(self, data):
        self.factory.len += len(data)
    def connectionLost(self, reason):
        self.factory.done = 1

class LargeBufferReaderClientFactory(protocol.ClientFactory):
    def __init__(self):
        self.done = 0
        self.len = 0
    def buildProtocol(self, addr):
        p = LargeBufferReaderProtocol()
        p.factory = self
        self.protocol = p
        return p
    
class LargeBufferTestCase(PortCleanerUpper):
    """Test that buffering large amounts of data works.
    """

    datalen = 60*1024*1024
    def testWriter(self):
        f = protocol.Factory()
        f.protocol = LargeBufferWriterProtocol
        f.done = 0
        f.problem = 0
        f.len = self.datalen
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        clientF = LargeBufferReaderClientFactory()
        reactor.connectTCP("127.0.0.1", n, clientF)

        while 1:
            rxlen = clientF.len
            try:
                spinUntil(lambda :f.done and clientF.done, timeout=30)
            except defer.TimeoutError:
                if clientF.len == rxlen:
                    raise
                # if we're still making progress, keep trying
                continue
            break

        self.failUnless(f.done, "writer didn't finish, it probably died")
        self.failUnless(clientF.len == self.datalen,
                        "client didn't receive all the data it expected "
                        "(%d != %d)" % (clientF.len, self.datalen))
        self.failUnless(clientF.done, "client didn't see connection dropped")


class MyHCProtocol(MyProtocol):

    implements(IHalfCloseableProtocol)
    
    readHalfClosed = False
    writeHalfClosed = False
    
    def readConnectionLost(self):
        self.readHalfClosed = True

    def writeConnectionLost(self):
        self.writeHalfClosed = True


class MyHCFactory(protocol.ServerFactory):

    called = 0

    def buildProtocol(self, addr):
        self.called += 1
        p = MyHCProtocol()
        p.factory = self
        self.protocol = p
        return p

    
class HalfCloseTestCase(PortCleanerUpper):
    """Test half-closing connections."""

    def setUp(self):
        PortCleanerUpper.setUp(self)
        self.f = f = MyHCFactory()
        self.p = p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.ports.append(p)
        spinUntil(lambda :p.connected)

        d = protocol.ClientCreator(reactor, MyHCProtocol).connectTCP(
            p.getHost().host, p.getHost().port)
        self.client = util.wait(d)
        self.assertEquals(self.client.transport.connected, 1)

    def tearDown(self):
        self.assertEquals(self.client.closed, 0)
        self.client.transport.loseConnection()
        self.p.stopListening()
        spinWhile(lambda :self.p.connected)

        self.assertEquals(self.client.closed, 1)
        # because we did half-close, the server also needs to
        # closed explicitly.
        self.assertEquals(self.f.protocol.closed, 0)
        self.f.protocol.transport.loseConnection()

        spinWhile(lambda :self.f.protocol.transport.connected)
        self.assertEquals(self.f.protocol.closed, 1)
    
    def testCloseWriteCloser(self):
        client = self.client
        f = self.f
        t = client.transport

        t.write("hello")
        spinUntil(lambda :len(t._tempDataBuffer) == 0)

        t.loseWriteConnection()
        spinUntil(lambda :t._writeDisconnected)

        self.assertEquals(client.closed, False)
        self.assertEquals(client.writeHalfClosed, True)
        self.assertEquals(client.readHalfClosed, False)

        spinUntil(lambda :f.protocol.readHalfClosed, timeout=1.0)

        w = client.transport.write
        w(" world")
        w("lalala fooled you")

        spinWhile(lambda :len(client.transport._tempDataBuffer) > 0)

        self.assertEquals(f.protocol.data, "hello")
        self.assertEquals(f.protocol.closed, False)
        self.assertEquals(f.protocol.readHalfClosed, True)

    def testWriteCloseNotification(self):
        f = self.f
        f.protocol.transport.loseWriteConnection()

        spinUntil(lambda :f.protocol.writeHalfClosed)
        spinUntil(lambda :self.client.readHalfClosed)

        self.assertEquals(f.protocol.readHalfClosed, False)
        

class HalfClose2TestCase(unittest.TestCase):

    def setUp(self):
        self.f = f = MyServerFactory()
        self.p = p = reactor.listenTCP(0, f, interface="127.0.0.1")
        reactor.iterate()
        reactor.iterate()
        # XXX we don't test server side yet since we don't do it yet
        d = protocol.ClientCreator(reactor, MyProtocol).connectTCP(
            p.getHost().host, p.getHost().port)
        d.addCallback(self._gotClient)
        return d

    def _gotClient(self, client):
        self.client = client

    def tearDown(self):
        self.client.transport.loseConnection()
        return self.p.stopListening()

    def testNoNotification(self):
        client = self.client
        f = self.f
        client.transport.write("hello")
        w = client.transport.write
        client.transport.loseWriteConnection()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(f.protocol.data, "hello")
        self.assertEquals(f.protocol.closed, True)

    def testShutdownException(self):
        client = self.client
        f = self.f
        f.protocol.transport.loseConnection()
        client.transport.write("X")
        client.transport.loseWriteConnection()
        spinUntil(lambda :f.protocol.closed, True)

class HalfClose3TestCase(PortCleanerUpper):
    """Test half-closing connections where notification code has bugs."""

    def setUp(self):
        PortCleanerUpper.setUp(self)
        self.f = f = MyHCFactory()
        self.p = p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.ports.append(p)
        spinUntil(lambda :p.connected)

        d = protocol.ClientCreator(reactor, MyHCProtocol).connectTCP(
            p.getHost().host, p.getHost().port)
        self.client = util.wait(d)
        self.assertEquals(self.client.transport.connected, 1)

    def aBug(self, *args):
        raise RuntimeError, "ONO I AM BUGGY CODE"
    
    def testReadNotificationRaises(self):
        self.f.protocol.readConnectionLost = self.aBug
        self.client.transport.loseWriteConnection()
        spinUntil(lambda :self.f.protocol.closed)
        # XXX client won't be closed?! why isn't server sending RST?
        # or maybe it is and we have a bug here.
        self.client.transport.loseConnection()
        log.flushErrors(RuntimeError)
    
    def testWriteNotificationRaises(self):
        self.client.writeConnectionLost = self.aBug
        self.client.transport.loseWriteConnection()
        spinUntil(lambda :self.client.closed)
        log.flushErrors(RuntimeError)


try:
    import resource
except ImportError:
    pass
else:
    numRounds = resource.getrlimit(resource.RLIMIT_NOFILE)[0] + 10
    ProperlyCloseFilesTestCase.numberRounds = numRounds
