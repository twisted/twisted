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

from twisted.internet import interfaces, reactor, protocol
from twisted.python import components
from twisted.protocols import loopback
import test_smtp

class TestClientFactory(protocol.ClientFactory):
    def startedConnecting(self, c):
        h = hasattr(c.transport, "socket") # have to split it up b/c transport
                                           # disappears on stopConnecting
                                            
        c.stopConnecting()
        assert h
    def buildProtocol(self, addr):
        return protocol.Protocol()

class Factory(protocol.Factory):
    def buildProtocol(self, addr):
        return protocol.Protocol()

class UnixSocketTestCase(test_smtp.LoopbackSMTPTestCase):
    """Test unix sockets."""
    
    def loopback(self, client, server):
        loopback.loopbackUNIX(client, server)

    def testDumber(self):
        filename = ".unixtest"
        l = reactor.listenUNIX(filename, Factory())
        reactor.connectUNIX(filename, TestClientFactory())
        for i in xrange(100):
            reactor.iterate()
        l.stopListening()

if not components.implements(reactor, interfaces.IReactorUNIX):
    del UnixSocketTestCase
