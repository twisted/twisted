# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""
This module contains the implementation of the TCP forwarding, which allows
clients and servers to forward arbitrary TCP data across the connection.

Maintainer: Paul Swartz
"""

import struct

from twisted.internet import protocol, reactor
from twisted.python import log

import common, channel

class SSHListenForwardingFactory(protocol.Factory):
    def __init__(self, connection, hostport, klass):
        self.conn = connection
        self.hostport = hostport # tuple
        self.klass = klass

    def buildProtocol(self, addr):
        channel = self.klass(conn = self.conn)
        client = SSHForwardingClient(channel)
        channel.client = client
        addrTuple = (addr.host, addr.port)
        channelOpenData = packOpen_direct_tcpip(self.hostport, addrTuple)
        self.conn.openChannel(channel, channelOpenData)
        return client

class SSHListenForwardingChannel(channel.SSHChannel):

    def channelOpen(self, specificData):
        log.msg('opened forwarding channel %s' % self.id)
        if len(self.client.buf)>1:
            b = self.client.buf[1:]
            self.write(b)
        self.client.buf = ''

    def openFailed(self, reason):
        self.closed()

    def dataReceived(self, data):
        self.client.transport.write(data)

    def eofReceived(self):
        self.client.transport.loseConnection()

    def closed(self):
        if hasattr(self, 'client'):
            log.msg('closing local forwarding channel %s' % self.id)
            self.client.transport.loseConnection()
            del self.client

class SSHListenClientForwardingChannel(SSHListenForwardingChannel):

    name = 'direct-tcpip'

class SSHListenServerForwardingChannel(SSHListenForwardingChannel):

    name = 'forwarded-tcpip'

class SSHConnectForwardingChannel(channel.SSHChannel):

    def __init__(self, hostport, *args, **kw):
        channel.SSHChannel.__init__(self, *args, **kw)
        self.hostport = hostport 
        self.client = None
        self.clientBuf = ''

    def channelOpen(self, specificData):
        cc = protocol.ClientCreator(reactor, SSHForwardingClient, self)
        log.msg("connecting to %s:%i" % self.hostport)
        cc.connectTCP(*self.hostport).addCallbacks(self._setClient, self._close)

    def _setClient(self, client):
        self.client = client
        log.msg("connected to %s:%i" % self.hostport)
        if self.clientBuf:
            self.client.transport.write(self.clientBuf)
            self.clientBuf = None
        if self.client.buf[1:]:
            self.write(self.client.buf[1:])
        self.client.buf = ''

    def _close(self, reason):
        log.msg("failed to connect: %s" % reason)
        self.loseConnection()

    def dataReceived(self, data):
        if self.client:
            self.client.transport.write(data)
        else:
            self.clientBuf += data

    def closed(self):
        if self.client:
            log.msg('closed remote forwarding channel %s' % self.id)
            if self.client.channel:
                self.loseConnection()
            self.client.transport.loseConnection()
            del self.client

def openConnectForwardingClient(remoteWindow, remoteMaxPacket, data, avatar):
    remoteHP, origHP = unpackOpen_direct_tcpip(data)
    return SSHConnectForwardingChannel(remoteHP, 
                                       remoteWindow=remoteWindow,
                                       remoteMaxPacket=remoteMaxPacket,
                                       avatar=avatar)

class SSHForwardingClient(protocol.Protocol):

    def __init__(self, channel):
        self.channel = channel
        self.buf = '\000'

    def dataReceived(self, data):
        if self.buf:
            self.buf += data
        else:
            self.channel.write(data)

    def connectionLost(self, reason):
        if self.channel:
            self.channel.loseConnection()
            self.channel = None


def packOpen_direct_tcpip((connHost, connPort), (origHost, origPort)):
    """Pack the data suitable for sending in a CHANNEL_OPEN packet.
    """
    conn = common.NS(connHost) + struct.pack('>L', connPort)
    orig = common.NS(origHost) + struct.pack('>L', origPort)
    return conn + orig

packOpen_forwarded_tcpip = packOpen_direct_tcpip

def unpackOpen_direct_tcpip(data):
    """Unpack the data to a usable format.
    """
    connHost, rest = common.getNS(data)
    connPort = int(struct.unpack('>L', rest[:4])[0])
    origHost, rest = common.getNS(rest[4:])
    origPort = int(struct.unpack('>L', rest[:4])[0])
    return (connHost, connPort), (origHost, origPort)

unpackOpen_forwarded_tcpip = unpackOpen_direct_tcpip
    
def packGlobal_tcpip_forward((host, port)):
    return common.NS(host) + struct.pack('>L', port)

def unpackGlobal_tcpip_forward(data):
    host, rest = common.getNS(data)
    port = int(struct.unpack('>L', rest[:4])[0])
    return host, port

"""This is how the data -> eof -> close stuff /should/ work.

debug3: channel 1: waiting for connection
debug1: channel 1: connected
debug1: channel 1: read<=0 rfd 7 len 0
debug1: channel 1: read failed
debug1: channel 1: close_read
debug1: channel 1: input open -> drain
debug1: channel 1: ibuf empty
debug1: channel 1: send eof
debug1: channel 1: input drain -> closed
debug1: channel 1: rcvd eof
debug1: channel 1: output open -> drain
debug1: channel 1: obuf empty
debug1: channel 1: close_write
debug1: channel 1: output drain -> closed
debug1: channel 1: rcvd close
debug3: channel 1: will not send data after close
debug1: channel 1: send close
debug1: channel 1: is dead
"""
