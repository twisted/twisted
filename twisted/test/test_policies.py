# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

"""Test code for policies."""
from __future__ import nested_scopes
from StringIO import StringIO

from twisted.trial import unittest

import time

from twisted.internet import protocol, reactor
from twisted.protocols import policies


class StringIOWithoutClosing(StringIO):
    def close(self): pass

class SimpleProtocol(protocol.Protocol):

    connected = disconnected = 0
    buffer = ""

    def connectionMade(self):
        self.connected = 1

    def connectionLost(self, reason):
        self.disconnected = 1

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



class ThrottlingTestCase(unittest.TestCase):

    def doIterations(self, count=5):
        for i in range(count):
            reactor.iterate()
            
    def testLimit(self):
        server = Server()
        c1, c2, c3, c4 = [SimpleProtocol() for i in range(4)]
        tServer = policies.ThrottlingFactory(server, 2)
        p = reactor.listenTCP(0, tServer, interface="127.0.0.1")
        n = p.getHost()[2]
        self.doIterations()

        for c in c1, c2, c3:
            reactor.connectTCP("127.0.0.1", n, SillyFactory(c))
            self.doIterations()

        self.assertEquals([c.connected for c in c1, c2, c3], [1, 1, 1])
        self.assertEquals([c.disconnected for c in c1, c2, c3], [0, 0, 1])
        self.assertEquals(len(tServer.protocols.keys()), 2)

        # disconnect one protocol and now another should be able to connect
        c1.transport.loseConnection()
        self.doIterations()
        reactor.connectTCP("127.0.0.1", n, SillyFactory(c4))
        self.doIterations()

        self.assertEquals(c4.connected, 1)
        self.assertEquals(c4.disconnected, 0)

        for c in c2, c4: c.transport.loseConnection()
        p.stopListening()
        self.doIterations()

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
    def setUp(self):
        self.failed = 0

    def testTimeout(self):
        # Create a server which times out inactive connections
        server = policies.TimeoutFactory(Server(), 3)
        port = reactor.listenTCP(0, server, interface="127.0.0.1")

        # Create a client tha sends and receive nothing
        client = SimpleProtocol()
        f = SillyFactory(client)
        reactor.connectTCP("127.0.0.1", port.getHost()[2], f)

        for i in range(10):
            reactor.iterate()
            self.assert_(client.connected)

        time.sleep(3.5)
        for i in range(3):
            reactor.iterate()
        self.assert_(client.disconnected)

        # Clean up
        port.loseConnection()
        for i in range(10):
            reactor.iterate()

    def testThatSendingDataAvoidsTimeout(self):
        # Create a server which times out inactive connections
        server = policies.TimeoutFactory(Server(), 2)
        port = reactor.listenTCP(0, server, interface="127.0.0.1")

        # Create a client that sends and receive nothing
        client = SimpleSenderProtocol(self)
        f = SillyFactory(client)
        f.protocol = client
        reactor.connectTCP("127.0.0.1", port.getHost()[2], f)
        reactor.callLater(3.5, client.finish)
        reactor.run()

        self.failUnlessEqual(self.failed, 0)
        self.failUnlessEqual(client.data, 'foo'*4)

    def testThatReadingDataAvoidsTimeout(self):
        # Create a server that sends occasionally
        server = SillyFactory(SimpleSenderProtocol(self))
        port = reactor.listenTCP(0, server, interface='127.0.0.1')

        clientFactory = policies.WrappingFactory(SillyFactory(SimpleProtocol()))
        port = reactor.connectTCP('127.0.0.1', port.getHost()[2], clientFactory)

        reactor.iterate()
        reactor.iterate()
        reactor.callLater(5, server.p.finish)
        reactor.run()

        self.failUnlessEqual(self.failed, 0)

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

    def testTimeout(self):
        p = TimeoutTester()
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))

        for i in range(10):
            reactor.iterate()
        self.failIf(p.timedOut)

        time.sleep(3.5)
        reactor.iterate()
        self.failUnless(p.timedOut)

    def testNoTimeout(self):
        p = TimeoutTester()
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))

        for i in range(10):
            reactor.iterate()
        self.failIf(p.timedOut)

        time.sleep(2)
        p.dataReceived('hello there')
        time.sleep(1.5)

        for i in range(10):
            reactor.iterate()
        self.failIf(p.timedOut)

        time.sleep(2)
        for i in range(10):
            reactor.iterate()
        self.failUnless(p.timedOut)

    def testResetTimeout(self):
        p = TimeoutTester()
        p.timeOut = None
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))
        
        p.setTimeout(1)
        self.assertEquals(p.timeOut, 1)
        
        for i in range(10):
            reactor.iterate()
        self.failIf(p.timedOut)

        time.sleep(1.1)
        reactor.iterate()
        self.failUnless(p.timedOut)
        p.connectionLost()
    
    def testCancelTimeout(self):
        p = TimeoutTester()
        p.timeOut = 5
        s = StringIOWithoutClosing()
        p.makeConnection(protocol.FileWrapper(s))
        
        p.setTimeout(None)
        self.assertEquals(p.timeOut, None)
        
        for i in range(10):
            reactor.iterate()
        self.failIf(p.timedOut)
        p.connectionLost()

    def testReturn(self):
        p = TimeoutTester()
        p.timeOut = 5
        
        self.assertEquals(p.setTimeout(10), 5)
        self.assertEquals(p.setTimeout(None), 10)
        self.assertEquals(p.setTimeout(1), None)
        self.assertEquals(p.timeOut, 1)
        
        p.connectionLost()
