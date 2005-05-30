# -*- test-case-name: twisted.test.test_unix -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet import interfaces, reactor, protocol, error, address, defer
from twisted.python import components, lockfile, failure
from twisted.protocols import loopback
from twisted.trial import unittest
from twisted.trial.util import spinWhile, spinUntil, wait
import stat, os


class MyProtocol(protocol.Protocol):
    made = closed = failed = 0
    data = ""
    def connectionMade(self):
        self.made = 1

    def dataReceived(self, data):
        self.data += data

    def connectionLost(self, reason):
        self.closed = 1

class TestClientFactory(protocol.ClientFactory):
    protocol = None

    def __init__(self, testcase, name):
        self.testcase = testcase
        self.name = name

    def buildProtocol(self, addr):
        self.testcase.assertEquals(address.UNIXAddress(self.name), addr)
        self.protocol = MyProtocol()
        return self.protocol

class Factory(protocol.Factory):
    protocol = stopped = None

    def __init__(self, testcase, name):
        self.testcase = testcase
        self.name = name

    def stopFactory(self):
        self.stopped = True

    def buildProtocol(self, addr):
        self.testcase.assertEquals(None, addr)
        self.protocol = p = MyProtocol()
        return p


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
                        spinUntil(lambda :p.disconnected)
                    except:
                        failure.Failure().printTraceback()


class UnixSocketTestCase(PortCleanerUpper):
    """Test unix sockets."""

    def testDumber(self):
        filename = self.mktemp()
        f = Factory(self, filename)
        l = reactor.listenUNIX(filename, f)
        tcf = TestClientFactory(self, filename)
        c = reactor.connectUNIX(filename, tcf)

        spinUntil(lambda :getattr(f.protocol, 'made', None) and
                          getattr(tcf.protocol, 'made', None))

        self._addPorts(l, c.transport, tcf.protocol.transport, f.protocol.transport)

    def testMode(self):
        filename = self.mktemp()
        f = Factory(self, filename)
        l = reactor.listenUNIX(filename, f, mode = 0600)
        self.assertEquals(stat.S_IMODE(os.stat(filename)[0]), 0600)
        tcf = TestClientFactory(self, filename)
        c = reactor.connectUNIX(filename, tcf)
        self._addPorts(l, c.transport)

    def testPIDFile(self):
        filename = self.mktemp()
        f = Factory(self, filename)
        l = reactor.listenUNIX(filename, f, mode = 0600, wantPID=1)
        self.assert_(lockfile.checkLock(filename))
        tcf = TestClientFactory(self, filename)
        c = reactor.connectUNIX(filename, tcf, checkPID=1)

        spinUntil(lambda :getattr(f.protocol, 'made', None) and
                          getattr(tcf.protocol, 'made', None))

        self._addPorts(l, c.transport, tcf.protocol.transport, f.protocol.transport)
        self.cleanPorts(*self.ports)

        self.assert_(not lockfile.checkLock(filename))


    def testRepr(self):
        filename = self.mktemp()
        f = Factory(self, filename)
        p = reactor.listenUNIX(filename, f)
        self.failIf(str(p).find(filename) == -1)

        def stoppedListening(ign):
            self.failIf(str(p).find(filename) != -1)

        return defer.maybeDeferred(p.stopListening).addCallback(stoppedListening)

class ClientProto(protocol.ConnectedDatagramProtocol):
    started = stopped = False
    gotback = None

    def stopProtocol(self):
        self.stopped = True

    def startProtocol(self):
        self.started = True

    def datagramReceived(self, data):
        self.gotback = data

class ServerProto(protocol.DatagramProtocol):
    started = stopped = False
    gotwhat = gotfrom = None

    def stopProtocol(self):
        self.stopped = True

    def startProtocol(self):
        self.started = True

    def datagramReceived(self, data, addr):
        self.gotfrom = addr
        self.gotwhat = data
        self.transport.write("hi back", addr)

class DatagramUnixSocketTestCase(PortCleanerUpper):
    """Test datagram UNIX sockets."""
    def testExchange(self):
        clientaddr = self.mktemp()
        serveraddr = self.mktemp()
        sp = ServerProto()
        cp = ClientProto()
        s = reactor.listenUNIXDatagram(serveraddr, sp)
        c = reactor.connectUNIXDatagram(serveraddr, cp, bindAddress = clientaddr)


        spinUntil(lambda:sp.started and cp.started)

        cp.transport.write("hi")

        spinUntil(lambda:sp.gotwhat == "hi" and cp.gotback == "hi back")

        s.stopListening()
        c.stopListening()
        os.unlink(clientaddr)
        os.unlink(serveraddr)
        spinWhile(lambda:s.connected and c.connected)
        self.failUnlessEqual("hi", sp.gotwhat)
        self.failUnlessEqual(clientaddr, sp.gotfrom)
        self.failUnlessEqual("hi back", cp.gotback)

    def testCannotListen(self):
        addr = self.mktemp()
        p = ServerProto()
        s = reactor.listenUNIXDatagram(addr, p)
        self.failUnlessRaises(error.CannotListenError, reactor.listenUNIXDatagram, addr, p)
        s.stopListening()
        os.unlink(addr)
    # test connecting to bound and connected (somewhere else) address

    def testRepr(self):
        filename = self.mktemp()
        f = ServerProto()
        p = reactor.listenUNIXDatagram(filename, f)
        self.failIf(str(p).find(filename) == -1)

        def stoppedListening(ign):
            self.failIf(str(p).find(filename) != -1)

        return defer.maybeDeferred(p.stopListening).addCallback(stoppedListening)


if not interfaces.IReactorUNIX(reactor, None):
    UnixSocketTestCase.skip = "This reactor does not support UNIX domain sockets"
if not interfaces.IReactorUNIXDatagram(reactor, None):
    DatagramUnixSocketTestCase.skip = "This reactor does not support UNIX datagram sockets"

