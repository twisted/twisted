# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""Test code for policies."""
from __future__ import nested_scopes
from StringIO import StringIO

from twisted.trial import unittest
from twisted.trial.util import fireWhenDoneFunc
from twisted.test.proto_helpers import StringTransportWithDisconnection
from twisted.test.time_helpers import Clock

import time

from twisted.internet import protocol, reactor, address, defer
from twisted.protocols import policies

class StringIOWithoutClosing(StringIO):
    def close(self): pass

class SimpleProtocol(protocol.Protocol):

    connected = disconnected = 0
    buffer = ""
    
    def __init__(self):
        self.dConnected = defer.Deferred()
        self.dDisconnected = defer.Deferred()

    def connectionMade(self):
        self.connected = 1
        self.dConnected.callback('')

    def connectionLost(self, reason):
        self.disconnected = 1
        self.dDisconnected.callback('')

    def dataReceived(self, data):
        self.buffer += data


class SillyFactory(protocol.ClientFactory):

    def __init__(self, p):
        self.p = p

    def buildProtocol(self, addr):
        return self.p


class EchoProtocol(protocol.Protocol):

    def pauseProducing(self):
        self.paused = time.time()

    def resumeProducing(self):
        self.resume = time.time()

    def stopProducing(self):
        pass

    def dataReceived(self, data):
        self.transport.write(data)


class Server(protocol.ServerFactory):

    protocol = EchoProtocol


class SimpleSenderProtocol(SimpleProtocol):
    finished = 0
    data = ''
    def __init__(self, testcase):
        self.testcase = testcase
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)
        self.writeSomething()
    def writeSomething(self):
        if self.disconnected:
            if not self.finished:
                self.fail()
            else:
                reactor.crash()
        if not self.disconnected:
            self.transport.write('foo')
            reactor.callLater(1, self.writeSomething)
    def finish(self):
        self.finished = 1
        self.transport.loseConnection()
    def fail(self):
        self.testcase.failed = 1
    def dataReceived(self, data):
        self.data += data


class WrapperTestCase(unittest.TestCase):
    def testProtocolFactoryAttribute(self):
        # Make sure protocol.factory is the wrapped factory, not the wrapping factory
        f = Server()
        wf = policies.WrappingFactory(f)
        p = wf.buildProtocol(address.IPv4Address('TCP', '127.0.0.1', 35))
        self.assertIdentical(p.wrappedProtocol.factory, f)


class ThrottlingTestCase(unittest.TestCase):

    def doIterations(self, count=5):
        for i in range(count):
            reactor.iterate()

    def testLimit(self):
        server = Server()
        c1, c2, c3, c4 = [SimpleProtocol() for i in range(4)]
        tServer = policies.ThrottlingFactory(server, 2)
        theDeferred = defer.Deferred()
        tServer.startFactory = fireWhenDoneFunc(theDeferred, tServer.startFactory)
        
        # Start listening
        p = reactor.listenTCP(0, tServer, interface="127.0.0.1")
        n = p.getHost().port
        
        def _connect123(results):
            for c in c1, c2, c3:
                p = reactor.connectTCP("127.0.0.1", n, SillyFactory(c))
            deferreds = [c.dConnected for c in c1, c2, c3]
            deferreds.append(c3.dDisconnected)
            return defer.DeferredList(deferreds)

        def _check123(results):
            self.assertEquals([c.connected for c in c1, c2, c3], [1, 1, 1])
            self.assertEquals([c.disconnected for c in c1, c2, c3], [0, 0, 1])
            self.assertEquals(len(tServer.protocols.keys()), 2)
            return results

        def _lose1(results):
            # disconnect one protocol and now another should be able to connect
            c1.transport.loseConnection()
            return c1.dDisconnected

        def _connect4(results):
            reactor.connectTCP("127.0.0.1", n, SillyFactory(c4))
            return c4.dConnected

        def _check4(results):
            self.assertEquals(c4.connected, 1)
            self.assertEquals(c4.disconnected, 0)
            return results

        def _cleanup(results):
            for c in c2, c4:
                c.transport.loseConnection()
            return defer.DeferredList([
                defer.maybeDeferred(p.stopListening),
                c2.dDisconnected,
                c4.dDisconnected])
        
        theDeferred.addCallback(_connect123)
        theDeferred.addCallback(_check123)
        theDeferred.addCallback(_lose1)
        theDeferred.addCallback(_connect4)
        theDeferred.addCallback(_check4)
        theDeferred.addCallback(_cleanup)
        return theDeferred

    def testWriteLimit(self):
        server = Server()
        c1, c2 = SimpleProtocol(), SimpleProtocol()

        # The throttling factory starts checking bandwidth immediately
        now = time.time()

        tServer = policies.ThrottlingFactory(server, writeLimit=10)
        port = reactor.listenTCP(0, tServer, interface="127.0.0.1")
        n = port.getHost()[2]
        reactor.iterate(); reactor.iterate()
        for c in c1, c2:
            reactor.connectTCP("127.0.0.1", n, SillyFactory(c))
            self.doIterations()

        for p in tServer.protocols.keys():
            p = p.wrappedProtocol
            self.assert_(isinstance(p, EchoProtocol))
            p.transport.registerProducer(p, 1)

        c1.transport.write("0123456789")
        c2.transport.write("abcdefghij")
        self.doIterations()

        self.assertEquals(c1.buffer, "0123456789")
        self.assertEquals(c2.buffer, "abcdefghij")
        self.assertEquals(tServer.writtenThisSecond, 20)

        # at this point server should've written 20 bytes, 10 bytes
        # above the limit so writing should be paused around 1 second
        # from 'now', and resumed a second after that

        for p in tServer.protocols.keys():
            self.assert_(not hasattr(p.wrappedProtocol, "paused"))
            self.assert_(not hasattr(p.wrappedProtocol, "resume"))

        while not hasattr(p.wrappedProtocol, "paused"):
            reactor.iterate()

        self.assertEquals(tServer.writtenThisSecond, 0)

        for p in tServer.protocols.keys():
            self.assert_(hasattr(p.wrappedProtocol, "paused"))
            self.assert_(not hasattr(p.wrappedProtocol, "resume"))
            self.assert_(abs(p.wrappedProtocol.paused - now - 1.0) < 0.1)

        while not hasattr(p.wrappedProtocol, "resume"):
            reactor.iterate()

        for p in tServer.protocols.keys():
            self.assert_(hasattr(p.wrappedProtocol, "resume"))
            self.assert_(abs(p.wrappedProtocol.resume -
                             p.wrappedProtocol.paused - 1.0) < 0.1)

        c1.transport.loseConnection()
        c2.transport.loseConnection()
        port.stopListening()
        for p in tServer.protocols.keys():
            p.loseConnection()
        self.doIterations()

    def testReadLimit(self):
        server = Server()
        c1, c2 = SimpleProtocol(), SimpleProtocol()
        now = time.time()
        tServer = policies.ThrottlingFactory(server, readLimit=10)
        port = reactor.listenTCP(0, tServer, interface="127.0.0.1")
        n = port.getHost()[2]
        self.doIterations()
        for c in c1, c2:
            reactor.connectTCP("127.0.0.1", n, SillyFactory(c))
            self.doIterations()

        c1.transport.write("0123456789")
        c2.transport.write("abcdefghij")
        self.doIterations()
        self.assertEquals(c1.buffer, "0123456789")
        self.assertEquals(c2.buffer, "abcdefghij")
        self.assertEquals(tServer.readThisSecond, 20)

        # we wrote 20 bytes, so after one second it should stop reading
        # and then a second later start reading again
        while time.time() - now < 1.05:
            reactor.iterate()
        self.assertEquals(tServer.readThisSecond, 0)

        # write some more - data should *not* get written for another second
        c1.transport.write("0123456789")
        c2.transport.write("abcdefghij")
        self.doIterations()
        self.assertEquals(c1.buffer, "0123456789")
        self.assertEquals(c2.buffer, "abcdefghij")
        self.assertEquals(tServer.readThisSecond, 0)

        while time.time() - now < 2.05:
            reactor.iterate()
        self.assertEquals(c1.buffer, "01234567890123456789")
        self.assertEquals(c2.buffer, "abcdefghijabcdefghij")
        c1.transport.loseConnection()
        c2.transport.loseConnection()
        port.stopListening()
        for p in tServer.protocols.keys():
            p.loseConnection()
        self.doIterations()

    # These fail intermittently.
    testReadLimit.skip = "Inaccurate tests are worse than no tests."
    testWriteLimit.skip = "Inaccurate tests are worse than no tests."


class TimeoutTestCase(unittest.TestCase):
    def setUpClass(self):
        self.clock = Clock()
        self.clock.install()


    def tearDownClass(self):
        self.clock.uninstall()


    def _serverSetup(self):
        # Create a server factory, get a protocol from it, connect it to a
        # transport, and return all three.
        wrappedFactory = protocol.ServerFactory()
        wrappedFactory.protocol = SimpleProtocol
        factory = policies.TimeoutFactory(wrappedFactory, 3)
        proto = factory.buildProtocol(address.IPv4Address('TCP', '127.0.0.1', 12345))
        transport = StringTransportWithDisconnection()
        transport.protocol = proto
        proto.makeConnection(transport)
        return factory, proto, transport


    def testTimeout(self):
        # Make sure that when a TimeoutFactory accepts a connection, it will
        # time out that connection if no data is read or written within the
        # timeout period.

        # Make the server-side connection
        factory, proto, transport = self._serverSetup()

        # Let almost 3 time units pass
        self.clock.pump(reactor, [0.0, 0.5, 1.0, 1.0, 0.4])
        self.failIf(proto.wrappedProtocol.disconnected)

        # Now let the timer elapse
        self.clock.pump(reactor, [0.0, 0.2])
        self.failUnless(proto.wrappedProtocol.disconnected)


    def testSendAvoidsTimeout(self):
        # Make sure that writing data to a transport from a protocol
        # constructed by a TimeoutFactory resets the timeout countdown.

        # Make the server-side connection
        factory, proto, transport = self._serverSetup()

        # Let half the countdown period elapse
        self.clock.pump(reactor, [0.0, 0.5, 1.0])
        self.failIf(proto.wrappedProtocol.disconnected)

        # Send some data (proto is the /real/ proto's transport, so this is
        # the write that gets called)
        proto.write('bytes bytes bytes')

        # More time passes, putting us past the original timeout
        self.clock.pump(reactor, [0.0, 1.0, 1.0])
        self.failIf(proto.wrappedProtocol.disconnected)

        # Make sure writeSequence delays timeout as well
        proto.writeSequence(['bytes'] * 3)

        # Tick tock
        self.clock.pump(reactor, [0.0, 1.0, 1.0])
        self.failIf(proto.wrappedProtocol.disconnected)

        # Don't write anything more, just let the timeout expire
        self.clock.pump(reactor, [0.0, 2.0])
        self.failUnless(proto.wrappedProtocol.disconnected)


    def testReceiveAvoidsTimeout(self):
        # Make sure that receiving data also resets the timeout countdown.

        # Make the server-side connection
        factory, proto, transport = self._serverSetup()

        # Let half the countdown period elapse
        self.clock.pump(reactor, [0.0, 1.0, 0.5])
        self.failIf(proto.wrappedProtocol.disconnected)

        # Some bytes arrive, they should reset the counter
        proto.dataReceived('bytes bytes bytes')

        # We pass the original timeout
        self.clock.pump(reactor, [0.0, 1.0, 1.0])
        self.failIf(proto.wrappedProtocol.disconnected)

        # Nothing more arrives though, the new timeout deadline is passed,
        # the connection should be dropped.
        self.clock.pump(reactor, [0.0, 1.0, 1.0])
        self.failUnless(proto.wrappedProtocol.disconnected)


class TimeoutTester(protocol.Protocol, policies.TimeoutMixin):
    timeOut  = 3
    timedOut = 0

    def connectionMade(self):
        self.setTimeout(self.timeOut)

    def dataReceived(self, data):
        self.resetTimeout()
        protocol.Protocol.dataReceived(self, data)

    def connectionLost(self, reason=None):
        self.setTimeout(None)

    def timeoutConnection(self):
        self.timedOut = 1


class TestTimeout(unittest.TestCase):

    def setUpClass(self):
        self.clock = Clock()
        self.clock.install()

    def tearDownClass(self):
        self.clock.uninstall()

    def testTimeout(self):
        p = TimeoutTester()
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))

        self.clock.pump(reactor, [0, 0.5, 1.0, 1.0])
        self.failIf(p.timedOut)
        self.clock.pump(reactor, [0, 1.0])
        self.failUnless(p.timedOut)

    def testNoTimeout(self):
        p = TimeoutTester()
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))

        self.clock.pump(reactor, [0, 0.5, 1.0, 1.0])
        self.failIf(p.timedOut)
        p.dataReceived('hello there')
        self.clock.pump(reactor, [0, 1.0, 1.0, 0.5])
        self.failIf(p.timedOut)
        self.clock.pump(reactor, [0, 1.0])
        self.failUnless(p.timedOut)

    def testResetTimeout(self):
        p = TimeoutTester()
        p.timeOut = None
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))

        p.setTimeout(1)
        self.assertEquals(p.timeOut, 1)

        self.clock.pump(reactor, [0, 0.9])
        self.failIf(p.timedOut)
        self.clock.pump(reactor, [0, 0.2])
        self.failUnless(p.timedOut)

    def testCancelTimeout(self):
        p = TimeoutTester()
        p.timeOut = 5
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))

        p.setTimeout(None)
        self.assertEquals(p.timeOut, None)

        self.clock.pump(reactor, [0, 5, 5, 5])
        self.failIf(p.timedOut)

    def testReturn(self):
        p = TimeoutTester()
        p.timeOut = 5

        self.assertEquals(p.setTimeout(10), 5)
        self.assertEquals(p.setTimeout(None), 10)
        self.assertEquals(p.setTimeout(1), None)
        self.assertEquals(p.timeOut, 1)

        # Clean up the DelayedCall
        p.setTimeout(None)


class LimitTotalConnectionsFactoryTestCase(unittest.TestCase):
    """Tests for policies.LimitTotalConnectionsFactory"""
    def testConnectionCounting(self):
        # Make a basic factory
        factory = policies.LimitTotalConnectionsFactory()
        factory.protocol = protocol.Protocol

        # connectionCount starts at zero
        self.assertEqual(0, factory.connectionCount)

        # connectionCount increments as connections are made
        p1 = factory.buildProtocol(None)
        self.assertEqual(1, factory.connectionCount)
        p2 = factory.buildProtocol(None)
        self.assertEqual(2, factory.connectionCount)

        # and decrements as they are lost
        p1.connectionLost(None)
        self.assertEqual(1, factory.connectionCount)
        p2.connectionLost(None)
        self.assertEqual(0, factory.connectionCount)

    def testConnectionLimiting(self):
        # Make a basic factory with a connection limit of 1
        factory = policies.LimitTotalConnectionsFactory()
        factory.protocol = protocol.Protocol
        factory.connectionLimit = 1

        # Make a connection
        p = factory.buildProtocol(None)
        self.assertNotEqual(None, p)
        self.assertEqual(1, factory.connectionCount)

        # Try to make a second connection, which will exceed the connection
        # limit.  This should return None, because overflowProtocol is None.
        self.assertEqual(None, factory.buildProtocol(None))
        self.assertEqual(1, factory.connectionCount)

        # Define an overflow protocol
        class OverflowProtocol(protocol.Protocol):
            def connectionMade(self):
                factory.overflowed = True
        factory.overflowProtocol = OverflowProtocol
        factory.overflowed = False

        # Try to make a second connection again, now that we have an overflow
        # protocol.  Note that overflow connections count towards the connection
        # count.
        op = factory.buildProtocol(None)
        op.makeConnection(None) # to trigger connectionMade
        self.assertEqual(True, factory.overflowed)
        self.assertEqual(2, factory.connectionCount)

        # Close the connections.
        p.connectionLost(None)
        self.assertEqual(1, factory.connectionCount)
        op.connectionLost(None)
        self.assertEqual(0, factory.connectionCount)


class WriteSequenceEchoProtocol(EchoProtocol):
    def dataReceived(self, bytes):
        if bytes.find('vector!') != -1:
            self.transport.writeSequence([bytes])
        else:
            EchoProtocol.dataReceived(self, bytes)

class TestLoggingFactory(policies.TrafficLoggingFactory):
    openFile = None
    def open(self, name):
        assert self.openFile is None, "open() called too many times"
        self.openFile = StringIO()
        return self.openFile

class LoggingFactoryTestCase(unittest.TestCase):
    def testThingsGetLogged(self):
        wrappedFactory = Server()
        wrappedFactory.protocol = WriteSequenceEchoProtocol
        t = StringTransportWithDisconnection()
        f = TestLoggingFactory(wrappedFactory, 'test')
        p = f.buildProtocol(('1.2.3.4', 5678))
        t.protocol = p
        p.makeConnection(t)

        v = f.openFile.getvalue()
        self.failUnless('*' in v, "* not found in %r" % (v,))
        self.failIf(t.value())

        p.dataReceived('here are some bytes')

        v = f.openFile.getvalue()
        self.assertNotEqual(-1, v.find("C 1: 'here are some bytes'"), "Expected client string not found in %r" % (v,))
        self.assertNotEqual(-1, v.find("S 1: 'here are some bytes'"), "Expected server string not found in %r" % (v,))
        self.assertEquals(t.value(), 'here are some bytes')

        t.clear()
        p.dataReceived('prepare for vector! to the extreme')
        v = f.openFile.getvalue()
        self.assertNotEqual(-1, v.find("SV 1: ['prepare for vector! to the extreme']"), "Expected server string not found in %r" % (v,))
        self.assertEquals(t.value(), 'prepare for vector! to the extreme')

        p.loseConnection()

        v = f.openFile.getvalue()
        self.assertNotEqual(-1, v.find('ConnectionDone'), "Connection done notification not found in %r" % (v,))
