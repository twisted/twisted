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

"""This module contains the implementation of the TCP forwarding, which allows
clients and servers to forward arbitrary TCP data across the connection.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import struct

from twisted.internet import protocol, reactor
from twisted.python import log

import common, connection

class SSHListenForwardingFactory(protocol.Factory):
    def __init__(self, connection, hostport, klass):
        self.conn = connection
        self.hostport = hostport # tuple
        self.klass = klass

    def buildProtocol(self, addr):
        channel = self.klass(conn = self.conn)
        client = SSHForwardingClient(channel)
        channel.client = client
        channelOpenData = packOpen_direct_tcpip(self.hostport, addr)
        self.conn.openChannel(channel, channelOpenData)
        return client

class SSHListenForwardingChannel(connection.SSHChannel):

    def channelOpen(self, specificData):
        log.msg('opened forwarding channel %s' % self.id)
        self.write('') # send the buffer

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

class SSHConnectForwardingChannel(connection.SSHChannel):

    def __init__(self, hostport, *args, **kw):
        connection.SSHChannel.__init__(self, *args, **kw)
        self.hostport = hostport
        self.client = None
        self.clientBuf = ''

    def channelOpen(self, specificData):
        cc = protocol.ClientCreator(reactor, SSHForwardingClient, self)
        log.msg("connecting to %s:%i" % self.hostport)
        cc.connectTCP(*self.hostport).addCallbacks(self._setClient, self._close)

    def _setClient(self, client):
        self.client = client
        if self.clientBuf:
            self.client.transport.write(self.clientBuf)
            self.clientBuf = None

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
            log.msg('closing remote forwarding channel %s' % self.id)
            self.client.transport.loseConnection()
            self.loseConnection()
            del self.client

class SSHForwardingClient(protocol.Protocol):

    def __init__(self, channel):
        self.channel = channel

    def dataReceived(self, data):
        self.channel.write(data)

    def connectionLost(self, reason):
        if self.channel:
            self.channel.loseConnection()
            del self.channel


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
