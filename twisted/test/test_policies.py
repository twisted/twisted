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

from pyunit import unittest

import time


from twisted.internet import protocol, reactor
from twisted.protocols import policies


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



class ThrottlingTestCase(unittest.TestCase):

    def testLimit(self):
        server = Server()
        c1, c2, c3, c4 = [SimpleProtocol() for i in range(4)]
        tServer = policies.ThrottlingFactory(server, 2)
        p = reactor.listenTCP(62345, tServer)
        reactor.iterate(); reactor.iterate()

        for c in c1, c2, c3:
            reactor.connectTCP("127.0.0.1", 62345, SillyFactory(c))
            reactor.iterate(); reactor.iterate()

        self.assertEquals([c.connected for c in c1, c2, c3], [1, 1, 1])
        self.assertEquals([c.disconnected for c in c1, c2, c3], [0, 0, 1])
        self.assertEquals(len(tServer.protocols.keys()), 2)
        
        # disconnect one protocol and now another should be able to connect
        c1.transport.loseConnection()
        reactor.iterate(); reactor.iterate()
        reactor.iterate(); reactor.iterate()
        reactor.connectTCP("127.0.0.1", 62345, SillyFactory(c4))
        reactor.iterate(); reactor.iterate()

        self.assertEquals(c4.connected, 1)
        self.assertEquals(c4.disconnected, 0)
        
        for c in c2, c4: c.transport.loseConnection()
        p.stopListening()
        reactor.iterate(); reactor.iterate()
        reactor.iterate(); reactor.iterate()

    def testWriteLimit(self):
        server = Server()
        c1, c2 = SimpleProtocol(), SimpleProtocol()
        tServer = policies.ThrottlingFactory(server, writeLimit=10)
        port = reactor.listenTCP(62346, tServer)
        reactor.iterate(); reactor.iterate()
        for c in c1, c2:
            reactor.connectTCP("127.0.0.1", 62346, SillyFactory(c))
            reactor.iterate(); reactor.iterate()

        for p in tServer.protocols.keys():
            p = p.wrappedProtocol
            self.assert_(isinstance(p, EchoProtocol))
            p.transport.registerProducer(p, 1)
        
        c1.transport.write("0123456789")
        c2.transport.write("abcdefghij")
        reactor.iterate(); reactor.iterate()
        reactor.iterate(); reactor.iterate()

        self.assertEquals(c1.buffer, "0123456789")
        self.assertEquals(c2.buffer, "abcdefghij")
        self.assertEquals(tServer.writtenThisSecond, 20)
        
        # at this point server should've written 20 bytes, 10 bytes above the limit
        # so writing should be paused around 1 second from now, and resumed a
        # second after that
        now = time.time()
        
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
            self.assert_(abs(p.wrappedProtocol.resume - p.wrappedProtocol.paused - 1.0) < 0.1)

        c1.transport.loseConnection()
        c2.transport.loseConnection()
        port.stopListening()
        reactor.iterate(); reactor.iterate()

    def testReadLimit(self):
        server = Server()
        c1, c2 = SimpleProtocol(), SimpleProtocol()
        tServer = policies.ThrottlingFactory(server, readLimit=10)
        port = reactor.listenTCP(62347, tServer)
        reactor.iterate(); reactor.iterate()
        for c in c1, c2:
            reactor.connectTCP("127.0.0.1", 62347, SillyFactory(c))
            reactor.iterate(); reactor.iterate()

        c1.transport.write("0123456789")
        c2.transport.write("abcdefghij")
        reactor.iterate(); reactor.iterate()
        reactor.iterate(); reactor.iterate()
        self.assertEquals(c1.buffer, "0123456789")
        self.assertEquals(c2.buffer, "abcdefghij")
        self.assertEquals(tServer.readThisSecond, 20)
        
        # we wrote 20 bytes, so after one second it should stop reading
        # and then a second later start reading again
        now = time.time()
        while time.time() - now < 1.05:
            reactor.iterate()
        self.assertEquals(tServer.readThisSecond, 0)
        
        # write some more - data should *not* get written for another second
        c1.transport.write("0123456789")
        c2.transport.write("abcdefghij")
        reactor.iterate(); reactor.iterate()
        reactor.iterate(); reactor.iterate()
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
        reactor.iterate(); reactor.iterate()
