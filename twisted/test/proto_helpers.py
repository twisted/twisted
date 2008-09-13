# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from twisted.protocols import basic
from twisted.internet import error


class LineSendingProtocol(basic.LineReceiver):
    lostConn = False

    def __init__(self, lines, start = True):
        self.lines = lines[:]
        self.response = []
        self.start = start

    def connectionMade(self):
        if self.start:
            map(self.sendLine, self.lines)

    def lineReceived(self, line):
        if not self.start:
            map(self.sendLine, self.lines)
            self.lines = []
        self.response.append(line)

    def connectionLost(self, reason):
        self.lostConn = True


class FakeDatagramTransport:
    noAddr = object()

    def __init__(self):
        self.written = []

    def write(self, packet, addr=noAddr):
        self.written.append((packet, addr))


class StringTransport:
    disconnecting = 0

    hostAddr = None
    peerAddr = None

    def __init__(self, hostAddress=None, peerAddress=None):
        self.clear()
        if hostAddress is not None:
            self.hostAddr = hostAddress
        if peerAddress is not None:
            self.peerAddr = peerAddress
        self.connected = True

    def clear(self):
        self.io = StringIO()

    def value(self):
        return self.io.getvalue()

    def write(self, data):
        if isinstance(data, unicode): # no, really, I mean it
            raise TypeError("Data must not be unicode")
        self.io.write(data)

    def writeSequence(self, data):
        self.io.write(''.join(data))

    def loseConnection(self):
        self.disconnecting = True

    def getPeer(self):
        if self.peerAddr is None:
            return ('StringIO', repr(self.io))
        return self.peerAddr

    def getHost(self):
        if self.hostAddr is None:
            return ('StringIO', repr(self.io))
        return self.hostAddr


class StringTransportWithDisconnection(StringTransport):
    def loseConnection(self):
        if self.connected:
            self.connected = False
            self.protocol.connectionLost(error.ConnectionDone("Bye."))

