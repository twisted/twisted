# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#
import errno, os
from twisted.python import log, reflect, components
from twisted.internet import base, fdesc, error
from twisted.pair import ethernet, ip

"""
You need Eunuchs for twisted.pair.tuntap to work.

Eunuchs is a library containing the missing manly parts of
UNIX API for Python.

Eunuchs is a library of Python extension that complement the standard
libraries in parts where full support for the UNIX API (or the Linux
API) is missing.

Most of the functions wrapped by Eunuchs are low-level, dirty, but
absolutely necessary functions for real systems programming. The aim is
to have the functions added to mainstream Python libraries.

Current list of functions included:

 - fchdir(2)
 - recvmsg(2) and sendmsg(2), including use of cmsg(3)
 - socketpair(2)
 - support for TUN/TAP virtual network interfaces

Eunuchs doesn't have a proper web home right now, but you can fetch
the source from http://ftp.debian.org/debian/pool/main/e/eunuch
-- debian users can just use 'apt-get install python-eunuchs'.

"""
from eunuchs.tuntap import opentuntap, TuntapPacketInfo, makePacketInfo

class TuntapPort(base.BasePort):
    """A Port that reads and writes packets from/to a TUN/TAP-device.

    TODO: Share general start/stop etc implementation details with
    twisted.internet.udp.Port.
    """
    maxThroughput = 256 * 1024 # max bytes we read in one eventloop iteration

    def __init__(self, interface, proto, maxPacketSize=8192, reactor=None):
        if components.implements(proto, ethernet.IEthernetProtocol):
            self.ethernet = 1
        else:
            self.ethernet = 0
            assert components.implements(proto, ip.IIPProtocol) # XXX: fix me
        base.BasePort.__init__(self, reactor)
        self.interface = interface
        self.protocol = proto
        self.maxPacketSize = maxPacketSize
        self.setLogStr()

    def __repr__(self):
        return "<%s on %s>" % (self.protocol.__class__, self.interface)

    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        self._bindSocket()
        self._connectToProtocol()

    def _bindSocket(self):
        log.msg("%s starting on %s"%(self.protocol.__class__, self.interface))
        try:
            fd, name = opentuntap(name=self.interface,
                                  ethernet=self.ethernet,
                                  packetinfo=0)
        except OSError, e:
            raise error.CannotListenError, (None, self.interface, e)
        fdesc.setNonBlocking(fd)
        self.interface = name
        self.connected = 1
        self.fd = fd

    def fileno(self):
        return self.fd

    def _connectToProtocol(self):
        self.protocol.makeConnection(self)
        self.startReading()

    def doRead(self):
        """Called when my socket is ready for reading."""
        read = 0
        while read < self.maxThroughput:
            try:
                data = os.read(self.fd, self.maxPacketSize)
                read += len(data)
#                pkt = TuntapPacketInfo(data)
                self.protocol.datagramReceived(data,
                                               partial=0 # pkt.isPartial(),
                                               )
            except OSError, e:
                if e.errno in (errno.EWOULDBLOCK,):
                    return
                else:
                    raise
            except IOError, e:
                if e.errno in (errno.EAGAIN, errno.EINTR):
                    return
                else:
                    raise
            except:
                log.deferr()

    def write(self, datagram):
        """Write a datagram."""
#        header = makePacketInfo(0, 0)
        try:
            return os.write(self.fd, datagram)
        except IOError, e:
            if e.errno == errno.EINTR:
                return self.write(datagram)
            elif e.errno == errno.EMSGSIZE:
                raise error.MessageLengthError, "message too long"
            elif e.errno == errno.ECONNREFUSED:
                raise error.ConnectionRefusedError
            else:
                raise

    def writeSequence(self, seq):
        self.write("".join(seq))

    def loseConnection(self):
        """Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.stopReading()
        if self.connected:
            from twisted.internet import reactor
            reactor.callLater(0, self.connectionLost)

    stopListening = loseConnection

    def connectionLost(self, reason=None):
        """Cleans up my socket.
        """
        log.msg('(Tuntap %s Closed)' % self.interface)
        base.BasePort.connectionLost(self, reason)
        if hasattr(self, "protocol"):
            # we won't have attribute in ConnectedPort, in cases
            # where there was an error in connection process
            self.protocol.doStop()
        self.connected = 0
        os.close(self.fd)
        del self.fd

    def setLogStr(self):
        self.logstr = reflect.qual(self.protocol.__class__) + " (TUNTAP)"

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return self.logstr

    def getHost(self):
        """
        Returns a tuple of ('TUNTAP', interface), indicating
        the servers address
        """
        return ('TUNTAP',)+self.interface
