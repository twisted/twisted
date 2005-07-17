
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
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

    def __init__(self):
        self.clear()

    def clear(self):
        self.io = StringIO()

    def value(self):
        return self.io.getvalue()

    def write(self, data):
        self.io.write(data)

    def writeSequence(self, data):
        self.io.write(''.join(data))

    def loseConnection(self):
        pass

    def getPeer(self):
        return ('StringIO', repr(self.io))

    def getHost(self):
        return ('StringIO', repr(self.io))


class StringTransportWithDisconnection(StringTransport):
    def loseConnection(self):
        self.protocol.connectionLost(error.ConnectionDone("Bye."))
