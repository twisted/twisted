# -*- test-case-name: twisted.test.test_udp -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 
from twisted.trial import unittest, util

from twisted.internet import protocol, reactor, error, defer, interfaces, address
from twisted.python import failure, components


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

    def connectionRefused(self):
        self.refused = 1


class GoodClient(Server):
    
    def connectionRefused(self):
        self.refused = 1


class PortCleanerUpper(unittest.TestCase):
    callToLoseCnx = 'loseConnection'
    def setUp(self):
        self.ports = []

    def tearDown(self):
        self.cleanPorts(*self.ports)

    def _addPorts(self, *ports):
        for p in ports:
            self.ports.append(p)

    def cleanPorts(self, *ports):
        for p in ports:
            if not hasattr(p, 'disconnected'):
                raise RuntimeError, ("You handed something to cleanPorts that"
                                     " doesn't have a disconnected attribute, dummy!")
            if not p.disconnected:
                d = getattr(p, self.callToLoseCnx)()
                if isinstance(d, defer.Deferred):
                    wait(d)
                else:
                    try:
                        util.spinUntil(lambda :p.disconnected)
                    except:
                        failure.Failure().printTraceback()


class OldConnectedUDPTestCase(PortCleanerUpper):
    def testStartStop(self):
        client = Client()
        port2 = reactor.connectUDP("127.0.0.1", 8888, client)
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(client.started, 1)
        self.assertEquals(client.stopped, 0)
        l = []
        self.assert_(repr(port2).find('test_udp.Client') > 0)
        defer.maybeDeferred(port2.stopListening).addCallback(l.append)
        reactor.iterate()
        reactor.iterate()
        self.assert_(repr(port2).find('test_udp.Client') > 0)
        self.assertEquals(client.stopped, 1)
        self.assertEquals(len(l), 1)
    testStartStop = util.suppressWarnings(testStartStop,
                                          ('use listenUDP and then transport.connect',
                                           DeprecationWarning))

    def testDNSFailure(self):
        client = Client()
        # if this domain exists, shoot your sysadmin
        reactor.connectUDP("xxxxxxxxx.zzzzzzzzz.yyyyy.", 8888, client)
        while not hasattr(client, 'failure'):
            reactor.iterate(0.05)
        self.assert_(client.failure.trap(error.DNSLookupError))
        self.assertEquals(client.stopped, 0)
        self.assertEquals(client.started, 0)
    testDNSFailure = util.suppressWarnings(testDNSFailure,
                                           ('use listenUDP and then transport.connect',
                                           DeprecationWarning))
    def testSendPackets(self):
        server = Server()
        port1 = reactor.listenUDP(0, server, interface="127.0.0.1")
        client = Client()
        port2 = reactor.connectUDP("127.0.0.1", server.transport.getHost().port, client)
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        server.transport.write("hello", (client.transport.getHost().host,
                                         client.transport.getHost().port))
        client.transport.write("world")
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(client.packets, ["hello"])
        self.assertEquals(server.packets, [("world", ("127.0.0.1", client.transport.getHost().port))])
        port1.stopListening(); port2.stopListening()
        reactor.iterate(); reactor.iterate()
    testSendPackets = util.suppressWarnings(testSendPackets,
                                            ('use listenUDP and then transport.connect',
                                             DeprecationWarning))

    def testConnectionRefused(self):
        # assume no one listening on port 80 UDP
        client = Client()
        port = reactor.connectUDP("127.0.0.1", 80, client)
        server = Server()
        port2 = reactor.listenUDP(0, server, interface="127.0.0.1")
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        client.transport.write("a")
        client.transport.write("b")
        server.transport.write("c", ("127.0.0.1", 80))
        server.transport.write("d", ("127.0.0.1", 80))
        server.transport.write("e", ("127.0.0.1", 80))
        server.transport.write("toserver", (port2.getHost().host,
                                            port2.getHost().port))
        server.transport.write("toclient", (port.getHost().host,
                                            port.getHost().port))
        reactor.iterate(); reactor.iterate()
        self.assertEquals(client.refused, 1)
        port.stopListening()
        port2.stopListening()
        reactor.iterate(); reactor.iterate()
    testConnectionRefused = util.suppressWarnings(testConnectionRefused,
                                                  ('use listenUDP and then transport.connect',
                                                   DeprecationWarning))


class UDPTestCase(unittest.TestCase):

    def testOldAddress(self):
        server = Server()
        p = reactor.listenUDP(0, server, interface="127.0.0.1")
        reactor.iterate()
        addr = p.getHost()
        self.assertEquals(addr, ('INET_UDP', addr.host, addr.port))
        p.stopListening()
    testOldAddress = util.suppressWarnings(testOldAddress,
                                           ('IPv4Address.__getitem__',
                                            DeprecationWarning))
    
    def testStartStop(self):
        server = Server()
        port1 = reactor.listenUDP(0, server, interface="127.0.0.1")
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(server.started, 1)
        self.assertEquals(server.stopped, 0)
        l = []
        defer.maybeDeferred(port1.stopListening).addCallback(l.append)
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(server.stopped, 1)
        self.assertEquals(len(l), 1)

    def testRebind(self):
        server = Server()
        p = reactor.listenUDP(0, server, interface="127.0.0.1")
        reactor.iterate()
        unittest.deferredResult(defer.maybeDeferred(p.stopListening))
        p = reactor.listenUDP(0, server, interface="127.0.0.1")
        reactor.iterate()
        unittest.deferredResult(defer.maybeDeferred(p.stopListening))
    
    def testBindError(self):
        server = Server()
        port = reactor.listenUDP(0, server, interface='127.0.0.1')
        n = port.getHost().port
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(server.transport.getHost(), address.IPv4Address('UDP', '127.0.0.1', n))
        server2 = Server()
        self.assertRaises(error.CannotListenError, reactor.listenUDP, n, server2, interface='127.0.0.1')
        port.stopListening()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

    def testSendPackets(self):
        server = Server()
        port1 = reactor.listenUDP(0, server, interface="127.0.0.1")
        client = GoodClient()
        port2 = reactor.listenUDP(0, client, interface="127.0.0.1")
        reactor.iterate()
        reactor.iterate()
        client.transport.connect("127.0.0.1", server.transport.getHost().port)
        clientAddr = client.transport.getHost()
        serverAddress = server.transport.getHost()
        server.transport.write("hello", (clientAddr.host, clientAddr.port))
        client.transport.write("a")
        client.transport.write("b", None)
        client.transport.write("c", (serverAddress.host, serverAddress.port))
        self.runReactor(0.4, True)
        self.assertEquals(client.packets, [("hello", ("127.0.0.1", server.transport.getHost().port))])
        addr = ("127.0.0.1", client.transport.getHost().port)
        self.assertEquals(server.packets, [("a", addr), ("b", addr), ("c", addr)])
        port1.stopListening(); port2.stopListening()
        reactor.iterate(); reactor.iterate()

    def testConnectionRefused(self):
        # assume no one listening on port 80 UDP
        client = GoodClient()
        port = reactor.listenUDP(0, client, interface="127.0.0.1")
        client.transport.connect("127.0.0.1", 80)
        server = Server()
        port2 = reactor.listenUDP(0, server, interface="127.0.0.1")
        self.runReactor(0.4, True)
        client.transport.write("a")
        client.transport.write("b")
        server.transport.write("c", ("127.0.0.1", 80))
        server.transport.write("d", ("127.0.0.1", 80))
        server.transport.write("e", ("127.0.0.1", 80))
        self.runReactor(0.4, True)
        self.assertEquals(client.refused, 1)
        port.stopListening()
        port2.stopListening()
        reactor.iterate(); reactor.iterate()

    def testBadConnect(self):
        client = GoodClient()
        port = reactor.listenUDP(0, client, interface="127.0.0.1")
        self.assertRaises(ValueError, client.transport.connect, "localhost", 80)
        client.transport.connect("127.0.0.1", 80)
        self.assertRaises(RuntimeError, client.transport.connect, "127.0.0.1", 80)
        port.stopListening()
        reactor.iterate()
        reactor.iterate()


    def testPortRepr(self):
        client = GoodClient()
        p = reactor.listenUDP(0, client)
        portNo = str(p.getHost().port)
        self.failIf(repr(p).find(portNo) == -1)
        def stoppedListening(ign):
            self.failIf(repr(p).find(portNo) != -1)
        return defer.maybeDeferred(p.stopListening).addCallback(stoppedListening)


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
        # multicast won't work if we listen over loopback, apparently
        self.port1 = reactor.listenMulticast(0, self.server)
        self.port2 = reactor.listenMulticast(0, self.client)
        reactor.iterate()
        reactor.iterate()
        self.client.transport.connect("127.0.0.1", self.server.transport.getHost().port)

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
        self.assertEquals(self.server.transport.getLoopbackMode(), 1)
        self.runUntilSuccess(self.server.transport.joinGroup, "225.0.0.250")
        self.server.transport.write("hello", ("225.0.0.250", self.server.transport.getHost().port))
        reactor.iterate()
        self.assertEquals(len(self.server.packets), 1)
        self.server.transport.setLoopbackMode(0)
        self.assertEquals(self.server.transport.getLoopbackMode(), 0)
        self.server.transport.write("hello", ("225.0.0.250", self.server.transport.getHost().port))
        reactor.iterate()
        self.assertEquals(len(self.server.packets), 1)
    
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
        c.transport.write("hello world", ("225.0.0.250", self.server.transport.getHost().port))
        
        iters = 0
        while iters < 100 and len(self.server.packets) == 0:
            reactor.iterate(0.05);
            iters += 1
        self.assertEquals(self.server.packets[0][0], "hello world")
        p.stopListening()

    def testMultiListen(self):
        c = Server()
        p = reactor.listenMulticast(0, c, listenMultiple=True)
        self.runUntilSuccess(self.server.transport.joinGroup, "225.0.0.250")
        portno = p.getHost().port
        c2 = Server()
        p2 = reactor.listenMulticast(portno, c2, listenMultiple=True)
        self.runUntilSuccess(self.server.transport.joinGroup, "225.0.0.250")
        c.transport.write("hello world", ("225.0.0.250", portno))

        self.runReactor(0.4, True)
        self.assertEquals(c.packets[0][0], "hello world")
        self.assertEquals(c2.packets[0][0], "hello world")
        p.stopListening()
        p2.stopListening()

    testMultiListen.skip = "on non-linux platforms it appears multiple processes can listen, but not multiple sockets in same process?"

if not interfaces.IReactorUDP(reactor, None):
    UDPTestCase.skip = "This reactor does not support UDP"
if not hasattr(reactor, "connectUDP"):
    OldConnectedUDPTestCase.skip = "This reactor does not support connectUDP"
if not interfaces.IReactorMulticast(reactor, None):
    MulticastTestCase.skip = "This reactor does not support multicast"

def checkForLinux22():
    import os
    if os.path.exists("/proc/version"):
        s = open("/proc/version").read()
        if s.startswith("Linux version"):
            s = s.split()[2]
            if s.split(".")[:2] == ["2", "2"]:
                MulticastTestCase.testInterface.im_func.todo = "figure out why this fails in linux 2.2"
checkForLinux22()
