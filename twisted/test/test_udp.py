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
from pyunit import unittest

from twisted.internet import protocol, reactor, error
from twisted.python import failure


class Mixin:

    started = 0
    stopped = 0

    def __init__(self):
        self.packets = []
    
    def startProtocol(self):
        self.started = 1

    def stopProtocol(self):
        self.stopped = 1


class Server(Mixin, protocol.DatagramProtocol):

    def datagramReceived(self, data, addr):
        self.packets.append((data, addr))


class Client(Mixin, protocol.ConnectedDatagramProtocol):
    
    def datagramReceived(self, data):
        self.packets.append(data)

    def connectionFailed(self, failure):
        self.failure = failure


class UDPTestCase(unittest.TestCase):

    def testStartStop(self):
        server = Server()
        port1 = reactor.listenUDP(0, server)
        client = Client()
        port2 = reactor.connectUDP("127.0.0.1", 8888, client)

        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(server.started, 1)
        self.assertEquals(client.started, 1)
        self.assertEquals(server.stopped, 0)
        self.assertEquals(client.stopped, 0)

        port1.stopListening()
        port2.stopListening()

        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(server.stopped, 1)
        self.assertEquals(client.stopped, 1)

    def testDNSFailure(self):
        client = Client()
        # if this domain exists, shoot your sysadmin
        reactor.connectUDP("xxxxxxxxx.zzzzzzzzz.yyyyy.", 8888, client)
        while not hasattr(client, 'failure'):
            reactor.iterate(0.05)
        self.assert_(client.failure.trap(error.DNSLookupError))
        self.assertEquals(client.stopped, 0)
        self.assertEquals(client.started, 0)

    def testBindError(self):
        server = Server()
        port = reactor.listenUDP(10123, server, interface='127.0.0.1')
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(server.transport.getHost(), ('INET_UDP', '127.0.0.1', 10123))
        server2 = Server()
        self.assertRaises(error.CannotListenError, reactor.listenUDP, 10123, server2, interface='127.0.0.1')
        port.stopListening()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

    def testSendPackets(self):
        server = Server()
        port1 = reactor.listenUDP(0, server)
        client = Client()
        port2 = reactor.connectUDP("127.0.0.1", server.transport.getHost()[2], client)
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        server.transport.write("hello", client.transport.getHost()[1:])
        client.transport.write("world")
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(client.packets, ["hello"])
        self.assertEquals(server.packets, [("world", ("127.0.0.1", client.transport.getHost()[2]))])
        port1.stopListening(); port2.stopListening()
        reactor.iterate(); reactor.iterate()


class MulticastTestCase(unittest.TestCase):

    def _resultSet(self, result, l):
        l.append(result)

    def runUntilSuccess(self, method, *args, **kwargs):
        l = []
        d = method(*args, **kwargs)
        d.addCallback(self._resultSet, l).addErrback(self._resultSet, l)
        while not l:
            reactor.iterate()
        if isinstance(l[0], failure.Failure):
            raise l[0].value

    def setUp(self):
        self.server = Server()
        self.client = Client()
        self.port1 = reactor.listenMulticast(0, self.server)
        self.port2 = reactor.connectMulticast("127.0.0.1", self.server.transport.getHost()[2], self.client)
        reactor.iterate()
        reactor.iterate()

    def tearDown(self):
        self.port1.stopListening()
        self.port2.stopListening()
        del self.server
        del self.client
        del self.port1
        del self.port2
        reactor.iterate()
        reactor.iterate()
    
    def testTTL(self):
        for o in self.client, self.server:
            self.assertEquals(o.transport.getTTL(), 1)
            o.transport.setTTL(2)
            self.assertEquals(o.transport.getTTL(), 2)

    def testLoopback(self):
        for o in self.client, self.server:
            self.assertEquals(o.transport.getLoopbackMode(), 1)
            o.transport.setLoopbackMode(0)
            self.assertEquals(o.transport.getLoopbackMode(), 0)
    
    def testInterface(self):
        for o in self.client, self.server:
            self.assertEquals(o.transport.getOutgoingInterface(), "0.0.0.0")
            self.runUntilSuccess(o.transport.setOutgoingInterface, "127.0.0.1")
            self.assertEquals(o.transport.getOutgoingInterface(), "127.0.0.1")

    def testJoinLeave(self):
        for o in self.client, self.server:
            self.runUntilSuccess(o.transport.joinGroup, "225.0.0.250")
            self.runUntilSuccess(o.transport.leaveGroup, "225.0.0.250")

    def testMulticast(self):
        c = Server()
        p = reactor.listenMulticast(0, c)
        self.runUntilSuccess(self.server.transport.joinGroup, "225.0.0.250")
        c.transport.write("hello world", ("225.0.0.250", self.server.transport.getHost()[2]))
        while len(self.server.packets) == 0:
            reactor.iterate(0.05);
        self.assertEquals(self.server.packets[0][0], "hello world")
        p.stopListening()

        
        
