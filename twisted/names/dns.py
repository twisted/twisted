
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

from twisted.protocols import dns, protocol
from twisted.internet import tcp, udp

DNS, TCP = range(2)

class DNSBoss:
    protocols = (dns.DNS, dns.DNSOnTCP)
    portPackages = (udp, tcp)

    def __init__( self ):
        self.pending = {}
        self.next = 0
        self.factories = [None, None]
        self.ports = [None, None]

    def createFactory(self, i):
        if self.factories[i] is None:
            self.factories[i] = protocol.Factory()
            self.factories[i].protocol = self.protocols[ i ]
            self.factories[i].boss = self

    def createUDPFactory(self):
        self.createFactory(0)

    def createTCPFactory(self):
        self.createFactory(1)

    def createBothFactories(self):
        self.createFactory(0)
        self.createFactory(1)

    def startListening(self, i, portNum=0):
        self.createFactory(i)
        if self.ports[i] is None:
            self.ports[i] = self.portPackages[i].Port(portNum, 
                                                      self.factories[i])
            self.ports[i].startListening()

    def startListeningUDP(self, portNum=0):
        self.startListening(0, portNum)

    def startListeningTCP(self, portNum=0):
        self.startListening(1, portNum)

    def startListeningBoth(self, portNum = 0):
        self.startListening(0, portNum)
        self.startListening( 1, portNum)

    def queryUDP(self, addr, name, callback):
        self.startListeningUDP()
        transport = self.ports[0].createConnection(addr)
        transport.protocol.query(name, callback)

    def queryTCP(self, addr, name, callback):
        self.createTCPFactory()
        protocol = self.factories[1].buildProtocol(addr)
        protocol.setQuery(name, callback)
        transport = tcp.Client(addr[0], addr[1], protocol)

    def stopReading(self, i):
        if self.ports[i] is not None:
            self.ports[i].stopReading()
        self.ports[i], self.factories[i] = None, None

    def stopReadingUDP(self):
        self.stopReading(0)

    def stopReadingTCP(self):
        self.stopReading(1)

    def stopReadingBoth(self):
        self.stopReading(0)
        self.stopReading(1)

    def addPending(self, callback):
        self.next = self.next + 1
        self.pending[self.next] = callback
        return self.next

    def accomplish(self, key, data):
        callback = self.pending.get(key)
        if callback is not None:
            del self.pending[key]
            callback(data)
