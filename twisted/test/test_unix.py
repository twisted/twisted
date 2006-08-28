# -*- test-case-name: twisted.test.test_unix -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import stat, os, sys
import socket

from twisted.internet import interfaces, reactor, protocol, error, address, defer, utils
from twisted.python import lockfile, failure
from twisted.protocols import loopback
from twisted.trial import unittest


class MyProtocol(protocol.Protocol):
    made = closed = failed = 0
    data = ""
    def connectionMade(self):
        self.deferred.callback(None)

    def dataReceived(self, data):
        self.data += data

    def connectionLost(self, reason):
        self.closed = 1

class TestClientFactory(protocol.ClientFactory):
    protocol = None

    def __init__(self, testcase, name):
        self.testcase = testcase
        self.name = name
        self.deferred = defer.Deferred()

    def buildProtocol(self, addr):
        self.testcase.assertEquals(address.UNIXAddress(self.name), addr)
        self.protocol = MyProtocol()
        self.protocol.deferred = self.deferred
        return self.protocol

class Factory(protocol.Factory):
    protocol = stopped = None

    def __init__(self, testcase, name, peername=''):
        self.testcase = testcase
        self.name = name
        self.peername = peername
        self.deferred = defer.Deferred()

    def stopFactory(self):
        self.stopped = True

    def buildProtocol(self, addr):
        # os.path.samefile fails on ('', '')
        if self.peername or addr.name:
            self.testcase.assertEquals(address.UNIXAddress(self.peername), addr,
                                       '%r != %r' % (self.peername, addr.name))
        else:
            self.testcase.assertEquals(self.peername, addr.name)
        self.protocol = p = MyProtocol()
        self.protocol.deferred = self.deferred
        return p


class FailedConnectionClientFactory(protocol.ClientFactory):
    def __init__(self, onFail):
        self.onFail = onFail

    def clientConnectionFailed(self, connector, reason):
        self.onFail.errback(reason)


class PortCleanerUpper(unittest.TestCase):
    callToLoseCnx = 'loseConnection'
    def setUp(self):
        self.ports = []

    def tearDown(self):
        return self.cleanPorts(*self.ports)

    def _addPorts(self, *ports):
        for p in ports:
            self.ports.append(p)

    def cleanPorts(self, *ports):
        ds = [ defer.maybeDeferred(p.loseConnection)
               for p in ports if p.connected ]
        return defer.gatherResults(ds)


class UnixSocketTestCase(PortCleanerUpper):
    """Test unix sockets."""

    def testPeerBind(self):
        """assert the remote endpoint (getPeer) on the receiving end matches
           the local endpoint (bind) on the connecting end, for unix sockets"""
        filename = self.mktemp()
        peername = self.mktemp()
        f = Factory(self, filename, peername=peername)
        l = reactor.listenUNIX(filename, f)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(peername)
        self._sock.connect(filename)            
        d = f.deferred
        def done(x):
            self._addPorts(l)
            self._sock.close()
            del self._sock
            return x
        d.addBoth(done)
        return d

    def testDumber(self):
        filename = self.mktemp()
        f = Factory(self, filename)
        l = reactor.listenUNIX(filename, f)
        tcf = TestClientFactory(self, filename)
        c = reactor.connectUNIX(filename, tcf)
        d = defer.gatherResults([f.deferred, tcf.deferred])
        d.addCallback(lambda x : self._addPorts(l, c.transport,
                                                tcf.protocol.transport,
                                                f.protocol.transport))
        return d

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
        self.failUnless(lockfile.isLocked(filename + ".lock"))
        tcf = TestClientFactory(self, filename)
        c = reactor.connectUNIX(filename, tcf, checkPID=1)
        d = defer.gatherResults([f.deferred, tcf.deferred])
        def _portStuff(ignored):
            self._addPorts(l, c.transport, tcf.protocol.transport,
                           f.protocol.transport)
            return self.cleanPorts(*self.ports)
        def _check(ignored):
            self.failIf(lockfile.isLocked(filename + ".lock"), 'locked')
        d.addCallback(_portStuff)
        d.addCallback(_check)
        return d
    

    def testSocketLocking(self):
        filename = self.mktemp()
        f = Factory(self, filename)
        l = reactor.listenUNIX(filename, f, wantPID=True)

        self.assertRaises(
            error.CannotListenError,
            reactor.listenUNIX, filename, f, wantPID=True)

        def stoppedListening(ign):
            l = reactor.listenUNIX(filename, f, wantPID=True)
            return l.stopListening()

        return l.stopListening().addCallback(stoppedListening)


    def _uncleanSocketTest(self, callback):
        self.filename = self.mktemp()
        source = ("from twisted.internet import protocol, reactor\n"
                  "reactor.listenUNIX(%r, protocol.ServerFactory(), wantPID=True)\n") % (self.filename,)
        env = {'PYTHONPATH': os.pathsep.join(sys.path)}

        d = utils.getProcessOutput(sys.executable, ("-u", "-c", source), env=env)
        d.addCallback(callback)
        return d


    def testUncleanServerSocketLocking(self):
        def ranStupidChild(ign):
            # If this next call succeeds, our lock handling is correct.
            p = reactor.listenUNIX(self.filename, Factory(self, self.filename), wantPID=True)
            return p.stopListening()
        return self._uncleanSocketTest(ranStupidChild)


    def testUncleanSocketLockingFromThePerspectiveOfAClientConnectingToTheDeadServerSocket(self):
        def ranStupidChild(ign):
            d = defer.Deferred()
            f = FailedConnectionClientFactory(d)
            c = reactor.connectUNIX(self.filename, f, checkPID=True)
            return self.assertFailure(d, error.BadFileError)
        return self._uncleanSocketTest(ranStupidChild)


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

    def __init__(self):
        self.deferredStarted = defer.Deferred()
        self.deferredGotBack = defer.Deferred()

    def stopProtocol(self):
        self.stopped = True

    def startProtocol(self):
        self.started = True
        self.deferredStarted.callback(None)

    def datagramReceived(self, data):
        self.gotback = data
        self.deferredGotBack.callback(None)

class ServerProto(protocol.DatagramProtocol):
    started = stopped = False
    gotwhat = gotfrom = None

    def __init__(self):
        self.deferredStarted = defer.Deferred()
        self.deferredGotWhat = defer.Deferred()

    def stopProtocol(self):
        self.stopped = True

    def startProtocol(self):
        self.started = True
        self.deferredStarted.callback(None)

    def datagramReceived(self, data, addr):
        self.gotfrom = addr
        self.transport.write("hi back", addr)
        self.gotwhat = data
        self.deferredGotWhat.callback(None)

class DatagramUnixSocketTestCase(PortCleanerUpper):
    """Test datagram UNIX sockets."""
    def testExchange(self):
        clientaddr = self.mktemp()
        serveraddr = self.mktemp()
        sp = ServerProto()
        cp = ClientProto()
        s = reactor.listenUNIXDatagram(serveraddr, sp)
        c = reactor.connectUNIXDatagram(serveraddr, cp, bindAddress = clientaddr)

        d = defer.gatherResults([sp.deferredStarted, cp.deferredStarted])
        def write(ignored):
            cp.transport.write("hi")
            return defer.gatherResults([sp.deferredGotWhat,
                                        cp.deferredGotBack])

        def cleanup(ignored):
            d1 = defer.maybeDeferred(s.stopListening)
            d1.addCallback(lambda x : os.unlink(clientaddr))
            d2 = defer.maybeDeferred(c.stopListening)
            d2.addCallback(lambda x : os.unlink(serveraddr))
            return defer.gatherResults([d1, d2])

        def _cbTestExchange(ignored):
            self.failUnlessEqual("hi", sp.gotwhat)
            self.failUnlessEqual(clientaddr, sp.gotfrom)
            self.failUnlessEqual("hi back", cp.gotback)

        d.addCallback(write)
        d.addCallback(cleanup)
        d.addCallback(_cbTestExchange)
        return d

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

