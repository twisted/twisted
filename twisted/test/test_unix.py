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

from twisted.internet import interfaces, reactor, protocol, error, address
from twisted.python import components, lockfile
from twisted.protocols import loopback
from twisted.trial import unittest
import test_smtp
import stat, os


class CancelProtocol(protocol.Protocol):

    def connectionMade(self):
        reactor.callLater(0.1, self.transport.loseConnection)


class TestClientFactory(protocol.ClientFactory):

    def __init__(self, testcase, name):
        self.testcase = testcase
        self.name = name
    
    def buildProtocol(self, addr):
        self.testcase.assertEquals(address.UNIXAddress(self.name), addr)
        return protocol.Protocol()


class Factory(protocol.Factory):

    def __init__(self, testcase, name):
        self.testcase = testcase
        self.name = name

    def buildProtocol(self, addr):
        self.testcase.assertEquals(None, addr)
        return CancelProtocol()


class UnixSocketTestCase(test_smtp.LoopbackSMTPTestCase):
    """Test unix sockets."""
    
    def loopback(self, client, server):
        loopback.loopbackUNIX(client, server)

    def testDumber(self):
        filename = self.mktemp()
        l = reactor.listenUNIX(filename, Factory(self, filename))
        reactor.connectUNIX(filename, TestClientFactory(self, filename))
        self.runReactor(0.2, True)
        l.stopListening()

    def testMode(self):
        filename = self.mktemp()
        l = reactor.listenUNIX(filename, Factory(self, filename), mode = 0600)
        self.assertEquals(stat.S_IMODE(os.stat(filename)[0]), 0600)
        reactor.connectUNIX(filename, TestClientFactory(self, filename))
        self.runReactor(0.2, True)
        l.stopListening()

    def testPIDFile(self):
        filename = self.mktemp()
        l = reactor.listenUNIX(filename, Factory(self, filename), mode = 0600, wantPID=1)
        self.assert_(lockfile.checkLock(filename))
        reactor.connectUNIX(filename, TestClientFactory(self, filename), checkPID=1)
        self.runReactor(0.2, True)
        l.stopListening()
        reactor.iterate(0.1)
        self.assert_(not lockfile.checkLock(filename))

class ClientProto(protocol.ConnectedDatagramProtocol):
    def datagramReceived(self, data):
        self.gotback = data

class ServerProto(protocol.DatagramProtocol):
    def datagramReceived(self, data, addr):
        self.gotfrom = addr
        self.gotwhat = data
        self.transport.write("hi back", addr)

class DatagramUnixSocketTestCase(unittest.TestCase):
    """Test datagram UNIX sockets."""
    def testExchange(self):
        clientaddr = self.mktemp()
        serveraddr = self.mktemp()
        sp = ServerProto()
        cp = ClientProto()
        s = reactor.listenUNIXDatagram(serveraddr, sp)
        c = reactor.connectUNIXDatagram(serveraddr, cp, bindAddress = clientaddr)
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        cp.transport.write("hi")
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        s.stopListening()
        c.stopListening()
        os.unlink(clientaddr)
        os.unlink(serveraddr)
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

if not components.implements(reactor, interfaces.IReactorUNIX):
    UnixSocketTestCase.skip = "This reactor does not support UNIX domain sockets"
if not components.implements(reactor, interfaces.IReactorUNIXDatagram):
    DatagramUnixSocketTestCase.skip = "This reactor does not support UNIX datagram sockets"

