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

from twisted.internet import protocol
from twisted.python import log

import common, connection

class SSHLocalForwardingFactory(protocol.Factory):
    def __init__(self, connection, hostport):
        self.conn = connection
        self.hostport = hostport # tuple

    def buildProtocol(self, addr):
        client = SSHLocalForwardingClient()
        channel = SSHLocalForwardingChannel(client, conn = self.conn)
        client.channel = channel
        channelOpenData = packOpen_direct_tcpip(self.hostport, addr)
        self.conn.openChannel(channel, channelOpenData)
        return client

class SSHLocalForwardingClient(protocol.Protocol):

    def dataReceived(self, data):
        self.channel.write(data)

    def connectionLost(self, reason):
        if hasattr(self, 'channel'):
            self.channel.loseConnection()
            del self.channel

class SSHLocalForwardingChannel(connection.SSHChannel):

    name = 'direct-tcpip'

    def __init__(self, client, *args, **kw):
        connection.SSHChannel.__init__(self, *args, **kw)
        self.client = client

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
            log.msg('closing forwarding channel %s' % self.id)
            self.client.transport.loseConnection()
            del self.client

def packOpen_direct_tcpip((connHost, connPort), (origHost, origPort)):
    """Pack the data suitable for sending in a CHANNEL_OPEN packet.
    """
    conn = common.NS(connHost) + struct.pack('>L', connPort)
    orig = common.NS(origHost) + struct.pack('>L', origPort)
    return conn + orig
