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

"""Resource limiting policies."""

# system imports
import sys, operator

# twisted imports
from twisted.internet.protocol import ServerFactory, Protocol, ClientFactory
from twisted.internet.interfaces import ITransport
from twisted.internet import reactor
from twisted.python import log


class ProtocolWrapper(Protocol):
    """Wraps protocol instances and acts as their transport as well."""
    
    __implements__ = ITransport,

    disconnecting = 0

    def __init__(self, factory, wrappedProtocol):
        self.wrappedProtocol = wrappedProtocol
        self.factory = factory

    # Transport relaying
    
    def write(self, data):
        self.transport.write(data)

    def writeSequence(self, data):
        self.transport.writeSequence(data)

    def loseConnection(self):
        self.disconnecting = 1
        self.transport.loseConnection()

    def getPeer(self):
        return self.transport.getPeer()

    def getHost(self):
        return self.transport.getHost()
    
    def registerProducer(self, producer, streaming):
        self.transport.registerProducer(producer, streaming)

    def unregisterProducer(self):
        self.transport.unregisterProducer()

    def stopConsuming(self):
        self.transport.stopConsuming()

    
    # Protocol relaying
    
    def connectionMade(self):
        self.factory.registerProtocol(self)
        self.wrappedProtocol.makeConnection(self)

    def dataReceived(self, data):
        self.wrappedProtocol.dataReceived(data)

    def connectionLost(self, reason):
        self.factory.unregisterProtocol(self)
        self.wrappedProtocol.connectionLost(reason)


class WrappingFactory(ClientFactory):
    """Wraps a factory and its protocols, and keeps track of them."""
    
    protocol = ProtocolWrapper
    
    def __init__(self, wrappedFactory):
        self.wrappedFactory = wrappedFactory
        self.protocols = {}

    def startedConnecting(self, connector):
        self.wrappedFactory.startedConnecting(connector)

    def clientConnectionFailed(self, connector, reason):
        self.wrappedFactory.clientConnectionFailed(connector, reason)

    def clientConnectionLost(self, connector, reason):
        self.wrappedFactory.clientConnectionLost(connector, reason)

    def buildProtocol(self, addr):
        return self.protocol(self, self.wrappedFactory.buildProtocol(addr))    

    def registerProtocol(self, p):
        """Called by protocol to register itself."""
        self.protocols[p] = 1

    def unregisterProtocol(self, p):
        """Called by protocols when they go away."""
        del self.protocols[p]


class ThrottlingProtocol(ProtocolWrapper):
    """Protocol for ThrottlingFactory."""

    # wrap API for tracking bandwidth
    
    def write(self, data):
        self.factory.registerWritten(len(data))
        ProtocolWrapper.write(self, data)

    def writeSequence(self, seq):
        self.factory.registerWritten(reduce(operator.add, map(len, seq)))
        ProtocolWrapper.writeSequence(self, seq)

    def dataReceived(self, data):
        self.factory.registerRead(len(data))
        ProtocolWrapper.dataReceived(self, data)

    def registerProducer(self, producer, streaming):
        self.producer = producer
        ProtocolWrapper.registerProducer(self, producer, streaming)

    def unregisterProducer(self):
        del self.producer
        ProtocolWrapper.unregisterProducer(self)

    
    def throttleReads(self):
        self.transport.stopReading()

    def unthrottleReads(self):
        self.transport.startReading()

    def throttleWrites(self):
        if hasattr(self, "producer"):
            self.producer.pauseProducing()

    def unthrottleWrites(self):
        if hasattr(self, "producer"):
            self.producer.resumeProducing()


class ThrottlingFactory(WrappingFactory):
    """Throttles bandwidth and number of connections.

    Write bandwidth will only be throttled if there is a producer
    registered.
    """

    protocol = ThrottlingProtocol
    
    def __init__(self, wrappedFactory, maxConnectionCount=sys.maxint, readLimit=None, writeLimit=None):
        WrappingFactory.__init__(self, wrappedFactory)
        self.connectionCount = 0
        self.maxConnectionCount = maxConnectionCount
        self.readLimit = readLimit # max bytes we should read per second
        self.writeLimit = writeLimit # max bytes we should write per second
        self.readThisSecond = 0
        self.writtenThisSecond = 0
        if readLimit is not None:
            self.checkReadBandwidth()
        if  writeLimit is not None:
            self.checkWriteBandwidth()
    
    def registerWritten(self, length):
        """Called by protocol to tell us more bytes were written."""
        self.writtenThisSecond += length

    def registerRead(self, length):
        """Called by protocol to tell us more bytes were read."""
        self.readThisSecond += length

    def checkReadBandwidth(self):
        """Checks if we've passed bandwidth limits."""
        if self.readThisSecond > self.readLimit:
            self.throttleReads()
            throttleTime = (float(self.readThisSecond) / self.readLimit) - 1.0
            reactor.callLater(throttleTime, self.unthrottleReads)
        self.readThisSecond = 0
        reactor.callLater(1, self.checkReadBandwidth)

    def checkWriteBandwidth(self):
        if self.writtenThisSecond > self.writeLimit:
            self.throttleWrites()
            throttleTime = (float(self.writtenThisSecond) / self.writeLimit) - 1.0
            reactor.callLater(throttleTime, self.unthrottleWrites)
        # reset for next round    
        self.writtenThisSecond = 0
        reactor.callLater(1, self.checkWriteBandwidth)

    def throttleReads(self):
        """Throttle reads on all protocols."""
        log.msg("Throttling reads on %s" % self)
        for p in self.protocols.keys():
            p.throttleReads()

    def unthrottleReads(self):
        """Stop throttling reads on all protocols."""
        log.msg("Stopped throttling reads on %s" % self)
        for p in self.protocols.keys():
            p.unthrottleReads()

    def throttleWrites(self):
        """Throttle writes on all protocols."""
        log.msg("Throttling writes on %s" % self)
        for p in self.protocols.keys():
            p.throttleWrites()

    def unthrottleWrites(self):
        """Stop throttling writes on all protocols."""
        log.msg("Stopped throttling writes on %s" % self)
        for p in self.protocols.keys():
            p.unthrottleWrites()

    def buildProtocol(self, addr):
        if self.connectionCount < self.maxConnectionCount:
            self.connectionCount += 1
            return WrappingFactory.buildProtocol(self, addr)
        else:
            log.msg("Max connection count reached!")
            return None

    def unregisterProtocol(self, p):
        WrappingFactory.unregisterProtocol(self, p)
        self.connectionCount -= 1


class SpewingProtocol(ProtocolWrapper):
    def dataReceived(self, data):
        log.msg("Received: %r" % data)
        ProtocolWrapper.dataReceived(self,data)

    def write(self, data):
        log.msg("Sending: %r" % data)
        ProtocolWrapper.write(self,data)

class SpewingFactory(WrappingFactory):
    protocol = SpewingProtocol
