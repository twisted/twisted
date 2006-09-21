# -*- test-case-name: twisted.test.test_tcp -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from __future__ import nested_scopes

"""Generic TCP tests."""

import socket, random, errno

from zope.interface import implements

from twisted.trial import unittest
from twisted.python import log

from twisted.internet import protocol, reactor, defer, interfaces
from twisted.internet import error
from twisted.internet.address import IPv4Address
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.protocols import policies

def loopUntil(predicate, interval=0):
    from twisted.internet import task
    d = defer.Deferred()
    def check():
        res = predicate()
        if res:
            d.callback(res)
    call = task.LoopingCall(check)
    def stop(result):
        call.stop()
        return result
    d.addCallback(stop)
    d2 = call.start(interval)
    d2.addErrback(d.errback)
    return d


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

    closedDeferred = None

    data = ""

    factory = None

    def connectionMade(self):
        self.made = 1
        if (self.factory is not None and
            self.factory.protocolConnectionMade is not None):
            d = self.factory.protocolConnectionMade
            self.factory.protocolConnectionMade = None
            d.callback(None)

    def dataReceived(self, data):
        self.data += data

    def connectionLost(self, reason):
        self.closed = 1
        if self.closedDeferred is not None:
            d, self.closedDeferred = self.closedDeferred, None
            d.callback(None)


class MyServerFactory(protocol.ServerFactory):

    called = 0

    protocolConnectionMade = None

    def buildProtocol(self, addr):
        self.called += 1
        p = MyProtocol()
        p.factory = self
        self.protocol = p
        return p


class MyClientFactory(protocol.ClientFactory):

    failed = 0
    stopped = 0

    def __init__(self):
        self.deferred = defer.Deferred()
        self.failDeferred = defer.Deferred()

    def clientConnectionFailed(self, connector, reason):
        self.failed = 1
        self.reason = reason
        self.failDeferred.callback(None)

    def clientConnectionLost(self, connector, reason):
        self.lostReason = reason
        self.deferred.callback(None)

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
        return self.cleanPorts(*self.ports)

    def cleanPorts(self, *ports):
        ds = [ defer.maybeDeferred(p.loseConnection)
               for p in ports if p.connected ]
        return defer.gatherResults(ds)


class ListeningTestCase(PortCleanerUpper):

    def testListen(self):
        f = MyServerFactory()
        p1 = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.failUnless(interfaces.IListeningPort.providedBy(p1))
        return p1.stopListening()

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
        return p1.stopListening()

    def testPortRepr(self):
        f = MyServerFactory()
        p = reactor.listenTCP(0, f)
        portNo = str(p.getHost().port)
        self.failIf(repr(p).find(portNo) == -1)
        def stoppedListening(ign):
            self.failIf(repr(p).find(portNo) != -1)
        d = defer.maybeDeferred(p.stopListening)
        return d.addCallback(stoppedListening)


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
        def check(x):
            self.assert_(clientF.protocol.made)
            self.assert_(port.disconnected)
            clientF.lostReason.trap(error.ConnectionDone)
        return clientF.deferred.addCallback(check)

    def _trapCnxDone(self, obj):
        getattr(obj, 'trap', lambda x: None)(error.ConnectionDone)

    def testTcpNoDelay(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")

        self.n = port.getHost().port
        self.ports.append(port)
        clientF = MyClientFactory()
        reactor.connectTCP("127.0.0.1", self.n, clientF)

        d = loopUntil(lambda: (f.called > 0 and
                               getattr(clientF, 'protocol', None) is not None))
        def check(x):
            for p in clientF.protocol, f.protocol:
                transport = p.transport
                self.assertEquals(transport.getTcpNoDelay(), 0)
                transport.setTcpNoDelay(1)
                self.assertEquals(transport.getTcpNoDelay(), 1)
                transport.setTcpNoDelay(0)
                self.assertEquals(transport.getTcpNoDelay(), 0)
        d.addCallback(check)
        d.addBoth(lambda _: self.cleanPorts(clientF.protocol.transport, port))
        return d

    def testTcpKeepAlive(self):
        f = MyServerFactory()
        port = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = port.getHost().port
        self.ports.append(port)
        clientF = MyClientFactory()
        reactor.connectTCP("127.0.0.1", self.n, clientF)

        d = loopUntil(lambda :(f.called > 0 and
                               getattr(clientF, 'protocol', None) is not None))
        def check(x):
            for p in clientF.protocol, f.protocol:
                transport = p.transport
                self.assertEquals(transport.getTcpKeepAlive(), 0)
                transport.setTcpKeepAlive(1)
                self.assertEquals(transport.getTcpKeepAlive(), 1)
                transport.setTcpKeepAlive(0)
                self.assertEquals(transport.getTcpKeepAlive(), 0)
        d.addCallback(check)
        d.addBoth(lambda _:self.cleanPorts(clientF.protocol.transport, port))
        return d

    def testFailing(self):
        clientF = MyClientFactory()
        # XXX we assume no one is listening on TCP port 69
        reactor.connectTCP("127.0.0.1", 69, clientF, timeout=5)
        def check(ignored):
            clientF.reason.trap(error.ConnectionRefusedError)
        return clientF.failDeferred.addCallback(check)


    def test_connectionRefusedErrorNumber(self):
        """
        Assert that the error number of the ConnectionRefusedError is
        ECONNREFUSED, and not some other socket related error.
        """

        # Bind a number of ports in the operating system.  We will attempt
        # to connect to these in turn immediately after closing them, in the
        # hopes that no one else has bound them in the mean time.  Any
        # connection which succeeds is ignored and causes us to move on to
        # the next port.  As soon as a connection attempt fails, we move on
        # to making an assertion about how it failed.  If they all succeed,
        # the test will fail.

        # It would be nice to have a simpler, reliable way to cause a
        # connection failure from the platform.
        #
        # On Linux (2.6.15), connecting to port 0 always fails.  FreeBSD
        # (5.4) rejects the connection attempt with EADDRNOTAVAIL.
        #
        # On FreeBSD (5.4), listening on a port and then repeatedly
        # connecting to it without ever accepting any connections eventually
        # leads to an ECONNREFUSED.  On Linux (2.6.15), a seemingly
        # unbounded number of connections succeed.

        serverSockets = []
        for i in xrange(10):
            serverSocket = socket.socket()
            serverSocket.bind(('127.0.0.1', 0))
            serverSocket.listen(1)
            serverSockets.append(serverSocket)
        random.shuffle(serverSockets)

        clientCreator = protocol.ClientCreator(reactor, protocol.Protocol)

        def tryConnectFailure():
            def connected(proto):
                """
                Darn.  Kill it and try again, if there are any tries left.
                """
                proto.transport.loseConnection()
                if serverSockets:
                    return tryConnectFailure()
                self.fail("Could not fail to connect - could not test errno for that case.")

            serverSocket = serverSockets.pop()
            serverHost, serverPort = serverSocket.getsockname()
            serverSocket.close()

            connectDeferred = clientCreator.connectTCP(serverHost, serverPort)
            connectDeferred.addCallback(connected)
            return connectDeferred

        refusedDeferred = tryConnectFailure()
        self.assertFailure(refusedDeferred, error.ConnectionRefusedError)
        def connRefused(exc):
            self.assertEqual(exc.osError, errno.ECONNREFUSED)
        refusedDeferred.addCallback(connRefused)
        def cleanup(passthrough):
            while serverSockets:
                serverSockets.pop().close()
            return passthrough
        refusedDeferred.addBoth(cleanup)
        return refusedDeferred


    def testConnectByServiceFail(self):
        try:
            reactor.connectTCP("127.0.0.1", "thisbetternotexist",
                               MyClientFactory())
        except error.ServiceNameUnknownError:
            return
        self.assert_(False, "connectTCP didn't raise ServiceNameUnknownError")
    
    def testConnectByService(self):
        serv = socket.getservbyname
        d = defer.succeed(None)
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

            d = loopUntil(
                lambda: (getattr(s, 'protocol', None) is not None and
                         getattr(cf, 'protocol', None) is not None))
            d.addBoth(lambda x:
                      self.cleanPorts(port, c.transport, cf.protocol.transport))
        finally:
            socket.getservbyname = serv
        d.addCallback(lambda x : self.assert_(s.called,
                                              '%s was not called' % (s,)))
        return d


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

        d = loopUntil(lambda :(p1.connected == 1))
        return d.addCallback(self._testServerStartStop, f, p1)

    def _testServerStartStop(self, ignored, f, p1):
        self.assertEquals((f.started, f.stopped), (1,0))
        # listen on two more ports
        p2 = reactor.listenTCP(0, f, interface='127.0.0.1')
        self.n2 = p2.getHost().port
        self.ports.append(p2)
        p3 = reactor.listenTCP(0, f, interface='127.0.0.1')
        self.n3 = p3.getHost().port
        self.ports.append(p3)
        d = loopUntil(lambda :(p2.connected == 1 and p3.connected == 1))
        
        def cleanup(x):
            self.assertEquals((f.started, f.stopped), (1, 0))
            # close two ports
            d1 = defer.maybeDeferred(p1.stopListening)
            d2 = defer.maybeDeferred(p2.stopListening)
            return defer.gatherResults([d1, d2])
        
        def assert1(ignored):
            self.assertEquals((f.started, f.stopped), (1, 0))
            return p3.stopListening()

        def assert2(ignored):
            self.assertEquals((f.started, f.stopped), (1, 1))
            return self.cleanPorts(*self.ports)

        d.addCallback(cleanup)
        d.addCallback(assert1)
        d.addCallback(assert2)
        return d


    def testClientStartStop(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.n = p.getHost().port
        self.ports.append(p)
        f.port = p

        d = loopUntil(lambda :p.connected)
        def check(ignored):
            factory = ClientStartStopFactory()
            reactor.connectTCP("127.0.0.1", self.n, factory)
            self.assert_(factory.started)
            return loopUntil(lambda :factory.stopped)
        d.addCallback(check)
        d.addBoth(lambda _: self.cleanPorts(*self.ports))
        return d


class ConnectorTestCase(PortCleanerUpper):

    def testConnectorIdentity(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        f.port = p

        d = loopUntil(lambda :p.connected)

        def check(ignored):
            l = []
            m = []
            factory = ClientStartStopFactory()
            factory.clientConnectionLost = lambda c, r: (l.append(c),
                                                         m.append(r))
            factory.startedConnecting = lambda c: l.append(c)
            connector = reactor.connectTCP("127.0.0.1", n, factory)
            self.failUnless(interfaces.IConnector.providedBy(connector))
            dest = connector.getDestination()
            self.assertEquals(dest.type, "TCP")
            self.assertEquals(dest.host, "127.0.0.1")
            self.assertEquals(dest.port, n)

            d = loopUntil(lambda :factory.stopped)
            d.addCallback(lambda _: m[0].trap(error.ConnectionDone))
            d.addCallback(lambda _: self.assertEquals(l,
                                                      [connector, connector]))
            return d
        d.addCallback(check)
        return d.addCallback(lambda x: self.cleanPorts(*self.ports))

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

        d = loopUntil(lambda :factory.stopped)
        def check(ignored):
            self.assertEquals(factory.failed, 1)
            factory.reason.trap(error.UserError)
            return self.cleanPorts(*self.ports)
        return d.addCallback(check)
        

    def testReconnect(self):
        f = ClosingFactory()
        p = reactor.listenTCP(0, f, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        f.port = p

        factory = MyClientFactory()
        d = loopUntil(lambda :p.connected)
        def step1(ignored):
            def clientConnectionLost(c, reason):
                c.connect()
            factory.clientConnectionLost = clientConnectionLost
            reactor.connectTCP("127.0.0.1", n, factory)
            return loopUntil(lambda :factory.failed)

        def step2(ignored):
            p = factory.protocol
            self.assertEquals((p.made, p.closed), (1, 1))
            factory.reason.trap(error.ConnectionRefusedError)
            self.assertEquals(factory.stopped, 1)
            return self.cleanPorts(*self.ports)

        return d.addCallback(step1).addCallback(step2)


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

        return self.cleanPorts(*self.ports)

    def _fireWhenDoneFunc(self, d, f):
        """Returns closure that when called calls f and then callbacks d.
        """
        from twisted.python import util as tputil
        def newf(*args, **kw):
            rtn = f(*args, **kw)
            d.callback('')
            return rtn
        return tputil.mergeFunctionMetadata(f, newf)

    def testClientBind(self):
        theDeferred = defer.Deferred()
        sf = MyServerFactory()
        sf.startFactory = self._fireWhenDoneFunc(theDeferred, sf.startFactory)
        p = reactor.listenTCP(0, sf, interface="127.0.0.1")
        self.ports.append(p)
        
        def _connect1(results):
            d = defer.Deferred()
            cf1 = MyClientFactory()
            cf1.buildProtocol = self._fireWhenDoneFunc(d, cf1.buildProtocol)
            reactor.connectTCP("127.0.0.1", p.getHost().port, cf1,
                               bindAddress=("127.0.0.1", 0))
            d.addCallback(_conmade, cf1)
            return d
        
        def _conmade(results, cf1):
            d = defer.Deferred()
            cf1.protocol.connectionMade = self._fireWhenDoneFunc(
                d, cf1.protocol.connectionMade)
            d.addCallback(_check1connect2, cf1)
            return d
        
        def _check1connect2(results, cf1):
            self.assertEquals(cf1.protocol.made, 1)
    
            d1 = defer.Deferred()
            d2 = defer.Deferred()
            port = cf1.protocol.transport.getHost().port
            cf2 = MyClientFactory()
            cf2.clientConnectionFailed = self._fireWhenDoneFunc(
                d1, cf2.clientConnectionFailed)
            cf2.stopFactory = self._fireWhenDoneFunc(d2, cf2.stopFactory)
            reactor.connectTCP("127.0.0.1", p.getHost().port, cf2,
                               bindAddress=("127.0.0.1", port))
            d1.addCallback(_check2failed, cf1, cf2)
            d2.addCallback(_check2stopped, cf1, cf2)
            dl = defer.DeferredList([d1, d2])
            dl.addCallback(_stop, cf1, cf2)
            return dl

        def _check2failed(results, cf1, cf2):
            self.assertEquals(cf2.failed, 1)
            cf2.reason.trap(error.ConnectBindError)
            self.assert_(cf2.reason.check(error.ConnectBindError))
            return results

        def _check2stopped(results, cf1, cf2):
            self.assertEquals(cf2.stopped, 1)
            return results

        def _stop(results, cf1, cf2):
            d = defer.Deferred()
            d.addCallback(_check1cleanup, cf1)
            cf1.stopFactory = self._fireWhenDoneFunc(d, cf1.stopFactory)
            cf1.protocol.transport.loseConnection()
            return d

        def _check1cleanup(results, cf1):
            self.assertEquals(cf1.stopped, 1)
            return self.cleanPorts(*self.ports)
        
        theDeferred.addCallback(_connect1)
        return theDeferred

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

        d = loopUntil(lambda :p2.state == "connected")
        def check(ignored):
            self.assertEquals(p1.getHost(), f2.address)
            self.assertEquals(p1.getHost(), f2.protocol.transport.getPeer())
            return p1.stopListening()
        def cleanup(ignored):
            self.ports.append(p2.transport)
            return self.cleanPorts(*self.ports)
        return d.addCallback(check).addCallback(cleanup)
        

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
        wrappedF = WiredFactory(f)
        p = reactor.listenTCP(0, wrappedF, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        clientF = WriterClientFactory()
        wrappedClientF = WiredFactory(clientF)
        reactor.connectTCP("127.0.0.1", n, wrappedClientF)

        def check(ignored):
            self.failUnless(f.done, "writer didn't finish, it probably died")
            self.failUnless(f.problem == 0, "writer indicated an error")
            self.failUnless(clientF.done,
                            "client didn't see connection dropped")
            expected = "".join(["Hello Cleveland!\n",
                                "Goodbye", " cruel", " world", "\n"])
            self.failUnless(clientF.data == expected,
                            "client didn't receive all the data it expected")
        d = defer.gatherResults([wrappedF.onDisconnect,
                                 wrappedClientF.onDisconnect])
        return d.addCallback(check)


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



class ConnectionLostNotifyingProtocol(protocol.Protocol):
    """
    Protocol which fires a Deferred which was previously passed to
    its initializer when the connection is lost.
    """
    def __init__(self, onConnectionLost):
        self.onConnectionLost = onConnectionLost


    def connectionLost(self, reason):
        self.onConnectionLost.callback(self)



class HandleSavingProtocol(ConnectionLostNotifyingProtocol):
    """
    Protocol which grabs the platform-specific socket handle and
    saves it as an attribute on itself when the connection is
    established.
    """
    def makeConnection(self, transport):
        """
        Save the platform-specific socket handle for future
        introspection.
        """
        self.handle = transport.getHandle()
        return protocol.Protocol.makeConnection(self, transport)



class ProperlyCloseFilesMixin:
    """
    Tests for platform resources properly being cleaned up.
    """
    def createServer(self, address, portNumber, factory):
        """
        Bind a server port to which connections will be made.  The server
        should use the given protocol factory.

        @return: The L{IListeningPort} for the server created.
        """
        raise NotImplementedError()


    def connectClient(self, address, portNumber, clientCreator):
        """
        Establish a connection to the given address using the given
        L{ClientCreator} instance.

        @return: A Deferred which will fire with the connected protocol instance.
        """
        raise NotImplementedError()


    def getHandleExceptionType(self):
        """
        Return the exception class which will be raised when an operation is
        attempted on a closed platform handle.
        """
        raise NotImplementedError()


    def getHandleErrorCode(self):
        """
        Return the errno expected to result from writing to a closed
        platform socket handle.
        """
        # These platforms have been seen to give EBADF:
        #
        #  Linux 2.4.26, Linux 2.6.15, OS X 10.4, FreeBSD 5.4
        #  Windows 2000 SP 4, Windows XP SP 2
        return errno.EBADF


    def test_properlyCloseFiles(self):
        """
        Test that lost connections properly have their underlying socket
        resources cleaned up.
        """
        onServerConnectionLost = defer.Deferred()
        serverFactory = protocol.ServerFactory()
        serverFactory.protocol = lambda: ConnectionLostNotifyingProtocol(
            onServerConnectionLost)
        serverPort = self.createServer('127.0.0.1', 0, serverFactory)

        onClientConnectionLost = defer.Deferred()
        serverAddr = serverPort.getHost()
        clientCreator = protocol.ClientCreator(
            reactor, lambda: HandleSavingProtocol(onClientConnectionLost))
        clientDeferred = self.connectClient(
            serverAddr.host, serverAddr.port, clientCreator)

        def clientConnected(client):
            """
            Disconnect the client.  Return a Deferred which fires when both
            the client and the server have received disconnect notification.
            """
            client.transport.loseConnection()
            return defer.gatherResults([
                onClientConnectionLost, onServerConnectionLost])
        clientDeferred.addCallback(clientConnected)

        def clientDisconnected((client, server)):
            """
            Verify that the underlying platform socket handle has been
            cleaned up.
            """
            expectedErrorCode = self.getHandleErrorCode()
            err = self.assertRaises(
                self.getHandleExceptionType(), client.handle.send, 'bytes')
            self.assertEqual(err.args[0], expectedErrorCode)
        clientDeferred.addCallback(clientDisconnected)

        def cleanup(passthrough):
            """
            Shut down the server port.  Return a Deferred which fires when
            this has completed.
            """
            result = defer.maybeDeferred(serverPort.stopListening)
            result.addCallback(lambda ign: passthrough)
            return result
        clientDeferred.addBoth(cleanup)

        return clientDeferred



class ProperlyCloseFilesTestCase(unittest.TestCase, ProperlyCloseFilesMixin):
    def createServer(self, address, portNumber, factory):
        return reactor.listenTCP(portNumber, factory, interface=address)


    def connectClient(self, address, portNumber, clientCreator):
        return clientCreator.connectTCP(address, portNumber)


    def getHandleExceptionType(self):
        return socket.error


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


class FireOnListenFactory(policies.WrappingFactory):
    protocol = lambda s, f, p : p
    
    def __init__(self, f):
        self.deferred = defer.Deferred()
        policies.WrappingFactory.__init__(self, f)

    def startFactory(self):
        self.deferred.callback(None)


class WiredForDeferreds(policies.ProtocolWrapper):
    def __init__(self, factory, wrappedProtocol):
        policies.ProtocolWrapper.__init__(self, factory, wrappedProtocol)

    def connectionMade(self):
        policies.ProtocolWrapper.connectionMade(self)
        self.factory.onConnect.callback(None)

    def connectionLost(self, reason):
        policies.ProtocolWrapper.connectionLost(self, reason)
        self.factory.onDisconnect.callback(None)


class WiredFactory(policies.WrappingFactory):
    protocol = WiredForDeferreds

    def __init__(self, wrappedFactory):
        policies.WrappingFactory.__init__(self, wrappedFactory)
        self.onConnect = defer.Deferred()
        self.onDisconnect = defer.Deferred()


class AddressTestCase(PortCleanerUpper):

    def getFreePort(self):
        """Get an empty port."""
        factory = FireOnListenFactory(protocol.ServerFactory())
        p = reactor.listenTCP(0, factory)
        def _stop(ignored):
            port = p.getHost().port
            d = defer.maybeDeferred(p.stopListening)
            return d.addCallback(lambda x:port)
        return factory.deferred.addCallback(_stop)
    
    def testBuildProtocol(self):
        d = self.getFreePort()
        d.addCallback(self._testBuildProtocol)
        return d

    def _testBuildProtocol(self, portno):
        f = AServerFactory(self, IPv4Address('TCP', '127.0.0.1', portno))
        wrappedF = FireOnListenFactory(f)
        p = reactor.listenTCP(0, wrappedF)
        self.ports.append(p)

        def client(ignored):
            acf = AClientFactory(self, IPv4Address("TCP", "127.0.0.1",
                                                   p.getHost().port))
            wired = WiredFactory(acf)
            reactor.connectTCP("127.0.0.1", p.getHost().port, wired,
                               bindAddress=("127.0.0.1", portno))
            d = wired.onConnect
            def _onConnect(ignored):
                self.ports.append(acf.protocol.transport)
                self.assert_(hasattr(self, "ran"))
                return wired.onDisconnect
            def _onDisconnect(ignored):
                del self.ran
            d.addCallback(_onConnect)
            d.addCallback(_onDisconnect)
            return d

        return wrappedF.deferred.addCallback(client)

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


class FireOnClose(policies.ProtocolWrapper):
    """A wrapper around a protocol that makes it fire a deferred when
    connectionLost is called.
    """
    def connectionLost(self, reason):
        policies.ProtocolWrapper.connectionLost(self, reason)
        self.factory.deferred.callback(None)


class FireOnCloseFactory(policies.WrappingFactory):
    protocol = FireOnClose

    def __init__(self, wrappedFactory):
        policies.WrappingFactory.__init__(self, wrappedFactory)
        self.deferred = defer.Deferred()

    
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
        wrappedF = FireOnCloseFactory(f)
        p = reactor.listenTCP(0, wrappedF, interface="127.0.0.1")
        n = p.getHost().port
        self.ports.append(p)
        clientF = LargeBufferReaderClientFactory()
        wrappedClientF = FireOnCloseFactory(clientF)
        reactor.connectTCP("127.0.0.1", n, wrappedClientF)

        d = defer.gatherResults([wrappedF.deferred, wrappedClientF.deferred])
        def check(ignored):
            self.failUnless(f.done, "writer didn't finish, it probably died")
            self.failUnless(clientF.len == self.datalen,
                            "client didn't receive all the data it expected "
                            "(%d != %d)" % (clientF.len, self.datalen))
            self.failUnless(clientF.done,
                            "client didn't see connection dropped")
        return d.addCallback(check)


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
    protocolConnectionMade = None

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
        d = loopUntil(lambda :p.connected)

        self.cf = protocol.ClientCreator(reactor, MyHCProtocol)

        d.addCallback(lambda _: self.cf.connectTCP(p.getHost().host,
                                                   p.getHost().port))
        d.addCallback(self._setUp)
        return d

    def _setUp(self, client):
        self.client = client
        self.clientProtoConnectionLost = self.client.closedDeferred = defer.Deferred()
        self.assertEquals(self.client.transport.connected, 1)
        # Wait for the server to notice there is a connection, too.
        return loopUntil(lambda: getattr(self.f, 'protocol', None) is not None)

    def tearDown(self):
        self.assertEquals(self.client.closed, 0)
        self.client.transport.loseConnection()
        d = defer.maybeDeferred(self.p.stopListening)
        d.addCallback(lambda ign: self.clientProtoConnectionLost)
        d.addCallback(self._tearDown)
        return d

    def _tearDown(self, ignored):
        self.assertEquals(self.client.closed, 1)
        # because we did half-close, the server also needs to
        # closed explicitly.
        self.assertEquals(self.f.protocol.closed, 0)
        d = defer.Deferred()
        def _connectionLost(reason):
            self.f.protocol.closed = 1
            d.callback(None)
        self.f.protocol.connectionLost = _connectionLost
        self.f.protocol.transport.loseConnection()
        d.addCallback(lambda x:self.assertEquals(self.f.protocol.closed, 1))
        return d
    
    def testCloseWriteCloser(self):
        client = self.client
        f = self.f
        t = client.transport

        t.write("hello")
        d = loopUntil(lambda :len(t._tempDataBuffer) == 0)
        def loseWrite(ignored):
            t.loseWriteConnection()
            return loopUntil(lambda :t._writeDisconnected)
        def check(ignored):
            self.assertEquals(client.closed, False)
            self.assertEquals(client.writeHalfClosed, True)
            self.assertEquals(client.readHalfClosed, False)
            return loopUntil(lambda :f.protocol.readHalfClosed)
        def write(ignored):
            w = client.transport.write
            w(" world")
            w("lalala fooled you")
            self.assertEquals(0, len(client.transport._tempDataBuffer))
            self.assertEquals(f.protocol.data, "hello")
            self.assertEquals(f.protocol.closed, False)
            self.assertEquals(f.protocol.readHalfClosed, True)
        return d.addCallback(loseWrite).addCallback(check).addCallback(write)

    def testWriteCloseNotification(self):
        f = self.f
        f.protocol.transport.loseWriteConnection()

        d = defer.gatherResults([
            loopUntil(lambda :f.protocol.writeHalfClosed),
            loopUntil(lambda :self.client.readHalfClosed)])
        d.addCallback(lambda _: self.assertEquals(
            f.protocol.readHalfClosed, False))
        return d
        

class HalfClose2TestCase(unittest.TestCase):

    def setUp(self):
        self.f = f = MyServerFactory()
        self.f.protocolConnectionMade = defer.Deferred()
        self.p = p = reactor.listenTCP(0, f, interface="127.0.0.1")

        # XXX we don't test server side yet since we don't do it yet
        d = protocol.ClientCreator(reactor, MyProtocol).connectTCP(
            p.getHost().host, p.getHost().port)
        d.addCallback(self._gotClient)
        return d

    def _gotClient(self, client):
        self.client = client
        # Now wait for the server to catch up - it doesn't matter if this
        # Deferred has already fired and gone away, in that case we'll
        # return None and not wait at all, which is precisely correct.
        return self.f.protocolConnectionMade

    def tearDown(self):
        self.client.transport.loseConnection()
        return self.p.stopListening()

    def testNoNotification(self):
        """
        TCP protocols support half-close connections, but not all of them
        support being notified of write closes.  In this case, test that
        half-closing the connection causes the peer's connection to be 
        closed.
        """
        self.client.transport.write("hello")
        self.client.transport.loseWriteConnection()
        self.f.protocol.closedDeferred = d = defer.Deferred()
        self.client.closedDeferred = d2 = defer.Deferred()
        d.addCallback(lambda x:
                      self.assertEqual(self.f.protocol.data, 'hello'))
        d.addCallback(lambda x: self.assertEqual(self.f.protocol.closed, True))
        return defer.gatherResults([d, d2])

    def testShutdownException(self):
        """
        If the other side has already closed its connection, 
        loseWriteConnection should pass silently.
        """
        self.f.protocol.transport.loseConnection()
        self.client.transport.write("X")
        self.client.transport.loseWriteConnection()
        self.f.protocol.closedDeferred = d = defer.Deferred()
        self.client.closedDeferred = d2 = defer.Deferred()
        d.addCallback(lambda x:
                      self.failUnlessEqual(self.f.protocol.closed, True))
        return defer.gatherResults([d, d2])


class HalfClose3TestCase(PortCleanerUpper):
    """Test half-closing connections where notification code has bugs."""

    def setUp(self):
        PortCleanerUpper.setUp(self)
        self.f = f = MyHCFactory()
        self.p = p = reactor.listenTCP(0, f, interface="127.0.0.1")
        self.ports.append(p)
        d = loopUntil(lambda :p.connected)
        def connect(ignored):
            c = protocol.ClientCreator(reactor, MyHCProtocol)
            return c.connectTCP(p.getHost().host, p.getHost().port)
        def setClient(client):
            self.client = client
            self.assertEquals(self.client.transport.connected, 1)
        d.addCallback(connect)
        d.addCallback(setClient)
        return d

    def aBug(self, *args):
        raise RuntimeError, "ONO I AM BUGGY CODE"
    
    def testReadNotificationRaises(self):
        self.f.protocol.readConnectionLost = self.aBug
        self.client.transport.loseWriteConnection()
        d = loopUntil(lambda :self.f.protocol.closed)
        def check(ignored):
            # XXX client won't be closed?! why isn't server sending RST?
            # or maybe it is and we have a bug here.
            self.client.transport.loseConnection()
            log.flushErrors(RuntimeError)
        return d.addCallback(check)
    
    def testWriteNotificationRaises(self):
        self.client.writeConnectionLost = self.aBug
        self.client.transport.loseWriteConnection()
        d = loopUntil(lambda :self.client.closed)
        d.addCallback(lambda _: log.flushErrors(RuntimeError))
        return d


try:
    import resource
except ImportError:
    pass
else:
    numRounds = resource.getrlimit(resource.RLIMIT_NOFILE)[0] + 10
    ProperlyCloseFilesTestCase.numberRounds = numRounds
