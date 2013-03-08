# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""Implement standard (and unused) TCP protocols.

These protocols are either provided by inetd, or are not provided at all.
"""

# system imports
import time, struct
from zope.interface import implements

# twisted import
from twisted.internet import protocol, interfaces


class Echo(protocol.Protocol):
    """As soon as any data is received, write it back (RFC 862)"""
    
    def dataReceived(self, data):
        self.transport.write(data)


class Discard(protocol.Protocol):
    """Discard any received data (RFC 863)"""
    
    def dataReceived(self, data):
        # I'm ignoring you, nyah-nyah
        pass


class Chargen(protocol.Protocol):
    """Generate repeating noise (RFC 864)"""
    noise = r'@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~ !"#$%&?'

    implements(interfaces.IProducer)

    def connectionMade(self):
        self.transport.registerProducer(self, 0)

    def resumeProducing(self):
        self.transport.write(self.noise)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class QOTD(protocol.Protocol):
    """Return a quote of the day (RFC 865)"""
    
    def connectionMade(self):
        self.transport.write(self.getQuote())
        self.transport.loseConnection()

    def getQuote(self):
        """Return a quote. May be overrriden in subclasses."""
        return "An apple a day keeps the doctor away.\r\n"

class Who(protocol.Protocol):
    """Return list of active users (RFC 866)"""
    
    def connectionMade(self):
        self.transport.write(self.getUsers())
        self.transport.loseConnection()
    
    def getUsers(self):
        """Return active users. Override in subclasses."""
        return "root\r\n"


class Daytime(protocol.Protocol):
    """Send back the daytime in ASCII form (RFC 867)"""
    
    def connectionMade(self):
        self.transport.write(time.asctime(time.gmtime(time.time())) + '\r\n')
        self.transport.loseConnection()


class Time(protocol.Protocol):
    """Send back the time in machine readable form (RFC 868)"""
    
    def connectionMade(self):
        # is this correct only for 32-bit machines?
        result = struct.pack("!i", int(time.time()))
        self.transport.write(result)
        self.transport.loseConnection()

