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

"""This module contains the implementation of the ssh-connection service, which
allows access to the shell and port-forwarding.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import struct, types

from twisted.internet import protocol, reactor, defer
from twisted.python import log
from twisted.conch import error
import service, common

class SSHConnection(service.SSHService):
    name = 'ssh-connection'

    def __init__(self):
        self.localChannelID = 0 # this is the current # to use for channel ID
        self.localToRemoteChannel = {} # local channel ID -> remote channel ID
        self.channels = {} # local channel ID -> subclass of SSHChannel
        self.channelsToRemoteChannel = {} # subclass of SSHChannel -> 
                                          # remote channel ID
        self.deferreds = {} # local channel -> list of deferreds for pending 
                            # requests or 'global' -> list of deferreds for 
                            # global requests
        self.remoteForwards = {} # list of ports we should accept from server
                            # (client only)
        self.listeners = {} # dict mapping (internface, port) -> listener

    # packet methods
    def ssh_GLOBAL_REQUEST(self, packet):
        requestType, rest = common.getNS(packet)
        wantReply, rest = ord(rest[0]), rest[1:]
        reply = MSG_REQUEST_FAILURE
        data = ''
        ret = self.gotGlobalRequest(requestType, rest)
        if ret:
            reply = MSG_REQUEST_SUCCESS
            if type(ret) in (types.TupleType, types.ListType):
                data = ret[1]
        else:
            reply = MSG_REQUEST_FAILURE
        if wantReply:
            self.transport.sendPacket(reply, data)

    def ssh_REQUEST_SUCCESS(self, packet):
        data = packet
        self.deferreds['global'].pop(0).callback(data)

    def ssh_REQUEST_FAILURE(self, packet):
        self.deferreds['global'].pop(0).errback(
            error.ConchError('global request failed'))

    def ssh_CHANNEL_OPEN(self, packet):
        channelType, rest = common.getNS(packet)
        senderChannel, windowSize, maxPacket = struct.unpack('>3L', rest[: 12])
        packet = rest[12:]
        channel = self.getChannel(channelType, windowSize, maxPacket, packet)
        if type(channel) != type((1, )):
            localChannel = self.localChannelID
            self.localChannelID+=1
            channel.id = localChannel
            self.channels[localChannel] = channel
            self.channelsToRemoteChannel[channel] = senderChannel
            self.localToRemoteChannel[localChannel] = senderChannel
            self.transport.sendPacket(MSG_CHANNEL_OPEN_CONFIRMATION, 
                struct.pack('>4L', senderChannel, localChannel, 
                    channel.localWindowSize, 
                    channel.localMaxPacket)+channel.specificData)
            channel.channelOpen('')
        else:
            reason, textualInfo = channel
            self.transport.sendPacket(MSG_CHANNEL_OPEN_FAILURE, 
                                struct.pack('>2L', senderChannel, reason)+ \
                               common.NS(textualInfo)+common.NS(''))

    def ssh_CHANNEL_OPEN_CONFIRMATION(self, packet):
        localChannel, remoteChannel, windowSize, maxPacket = struct.unpack('>4L', packet[: 16])
        specificData = packet[16:]
        channel = self.channels[localChannel]
        channel.conn = self
        self.localToRemoteChannel[localChannel] = remoteChannel
        self.channelsToRemoteChannel[channel] = remoteChannel
        channel.remoteWindowLeft = windowSize
        channel.remoteMaxPacket = maxPacket
        channel.channelOpen(specificData)

    def ssh_CHANNEL_OPEN_FAILURE(self, packet):
        localChannel, reasonCode = struct.unpack('>2L', packet[: 8])
        reasonDesc = common.getNS(packet[8:])[0]
        channel = self.channels[localChannel]
        del self.channels[localChannel]
        channel.conn = self
        reason = error.ConchError(reasonDesc)
        reason.desc = reasonDesc
        reason.code = reasonCode
        channel.openFailed(reason)

    def ssh_CHANNEL_WINDOW_ADJUST(self, packet):
        localChannel, bytesToAdd = struct.unpack('>2L', packet[: 8])
        self.channels[localChannel].addWindowBytes(bytesToAdd)

    def ssh_CHANNEL_DATA(self, packet):
        localChannel = struct.unpack('>L', packet[: 4])[0]
        channel = self.channels[localChannel]
        data = common.getNS(packet[4:])[0]
        # XXX should this move to dataReceived to put client in charge?
        if len(data) > channel.localWindowLeft:
            data = data[: channel.localWindowLeft]
        channel.localWindowLeft-=len(data)
        if channel.localWindowLeft < channel.localWindowSize/2:
            self.adjustWindow(channel, channel.localWindowSize- \
                               channel.localWindowLeft)
            #log.msg('local window left: %s/%s' % (channel.localWindowLeft,
            #                                    channel.localWindowSize))
        channel.dataReceived(data)

    def ssh_CHANNEL_EXTENDED_DATA(self, packet):
        log.msg('extended data here')
        localChannel, typeCode = struct.unpack('>2L', packet[: 8])
        data = common.getNS(packet[8:])[0]
        self.channels[localChannel].extReceived(typeCode, data)

    def ssh_CHANNEL_EOF(self, packet):
        localChannel = struct.unpack('>L', packet[: 4])[0]
        self.channels[localChannel].eofReceived()

    def ssh_CHANNEL_CLOSE(self, packet):
        localChannel = struct.unpack('>L', packet[: 4])[0]
        channel = self.channels[localChannel]
        channel.closed()
        del self.localToRemoteChannel[localChannel]
        del self.channels[localChannel]
        try:
            del self.channelsToRemoteChannel[channel]
        except KeyError:
            pass # we'd already closed this end


    def ssh_CHANNEL_REQUEST(self, packet):
        localChannel = struct.unpack('>L', packet[: 4])[0]
        requestType, rest = common.getNS(packet[4:])
        wantReply = ord(rest[0])
        if self.channels[localChannel].requestReceived(requestType, rest[1:]):
            reply = MSG_CHANNEL_SUCCESS
        else:
            reply = MSG_CHANNEL_FAILURE
        if wantReply:
            self.transport.sendPacket(reply, struct.pack('>L', 
                                    self.localToRemoteChannel[localChannel]))

    def ssh_CHANNEL_SUCCESS(self, packet):
        localChannel = struct.unpack('>L', packet[: 4])[0]
        if self.deferreds.has_key(localChannel):
            d = self.deferreds[localChannel].pop(0)
            d.callback(packet[4:])

    def ssh_CHANNEL_FAILURE(self, packet):
        localChannel = struct.unpack('>L', packet[: 4])[0]
        if self.deferreds.has_key(localChannel):
            d = self.deferreds[localChannel].pop(0)
            d.errback(error.ConchError('channel request failed'))

    # methods for users of the connection to call

    def sendGlobalRequest(self, request, data, wantReply = 0):
        self.transport.sendPacket(MSG_GLOBAL_REQUEST,
                                  common.NS(request)
                                  + (wantReply and '\xff' or '\x00')
                                  + data)
        if wantReply:
            d = defer.Deferred()
            self.deferreds.setdefault('global', []).append(d)
            return d

    def openChannel(self, channel, extra = ''):
        log.msg('opening channel %s with %s %s'%(self.localChannelID, 
                channel.localWindowSize, channel.localMaxPacket))
        self.transport.sendPacket(MSG_CHANNEL_OPEN, common.NS(channel.name)
                    +struct.pack('>3L', self.localChannelID, 
                    channel.localWindowSize, channel.localMaxPacket)
                    +extra)
        channel.id = self.localChannelID
        self.channels[self.localChannelID] = channel
        self.localChannelID+=1

    def sendRequest(self, channel, requestType, data, wantReply = 0):
        log.msg('sending request for channel %s, request %s'%(channel.id, requestType))

        self.transport.sendPacket(MSG_CHANNEL_REQUEST, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel])
                                  + common.NS(requestType)+chr(wantReply)
                                  + data)
        if wantReply:
            d = defer.Deferred()
            self.deferreds.setdefault(channel.id, []).append(d)
            return d

    def adjustWindow(self, channel, bytesToAdd):
        if channel not in self.channelsToRemoteChannel.keys():
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_WINDOW_ADJUST, struct.pack('>2L', 
                                    self.channelsToRemoteChannel[channel], 
                                    bytesToAdd))
        channel.localWindowLeft+=bytesToAdd

    def sendData(self, channel, data):
        if channel not in self.channelsToRemoteChannel.keys():
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel])+ \
                                   common.NS(data))

    def sendExtendedData(self, channel, dataType, data):
        if channel not in self.channelsToRemoteChannel.keys():
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>2L', 
                                    self.channelsToRemoteChannel[channel]), 
                                    dataType+common.NS(data))

    def sendEOF(self, channel):
        if channel not in self.channelsToRemoteChannel.keys():
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_EOF, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel]))

    def sendClose(self, channel):
        if channel not in self.channelsToRemoteChannel.keys():
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_CLOSE, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel]))
        del self.channelsToRemoteChannel[channel]

    # methods to override
    def getChannel(self, channelType, windowSize, maxPacket, data):
        """the other side requested a channel of some sort.
        channelType is the string describing the channel
        windowSize is the initial size of the remote window
        maxPacket is the largest size of packet this channel should send
        data is any other packet data

        either this returns something that is a subclass of SSHChannel (although
        this isn't enforced), or a tuple of errorCode, errorString.
        """
        if self.transport.isClient and channelType != 'forwarded-tcpip':
            return OPEN_ADMINISTRATIVELY_PROHIBITED, 'not on the client bubba'
        if channelType == 'session':
            return SSHSession(remoteWindow = windowSize, 
                              remoteMaxPacket = maxPacket, 
                              conn = self)
        elif channelType == 'forwarded-tcpip':
            remoteHP, origHP = forwarding.unpackOpen_forwarded_tcpip(data)
            if self.remoteForwards.has_key(remoteHP[1]):
                connectHP = self.remoteForwards[remoteHP[1]]
                return forwarding.SSHConnectForwardingChannel(connectHP,
                                                    remoteWindow = windowSize,
                                                    remoteMaxPacket = maxPacket,
                                                    conn = self)
            else:
                return OPEN_CONNECT_FAILED, "don't know about that port"
        elif channelType == 'direct-tcpip':
            remoteHP, origHP = forwarding.unpackOpen_direct_tcpip(data)
            return forwarding.SSHConnectForwardingChannel(remoteHP,
                                                remoteWindow = windowSize,
                                                remoteMaxPacket = maxPacket,
                                                conn = self)
        else:
            return OPEN_UNKNOWN_CHANNEL_TYPE, "don't know %s"%channelType

    def gotGlobalRequest(self, requestType, data):
        """
        We got a global request.  pretty much, this is just used by the client
        to request that we forward a port from the server to the client.
        returns either:
            - 1: request accepted
            - 1, <data>: request accepted with request specific data
            - 0: request denied
        """
        if self.transport.isClient:
            return 0 # no such luck
        elif requestType == 'tcpip-forward':
            hostToBind, portToBind = forwarding.unpackGlobal_tcpip_forward(data)
            if portToBind < 1024:
                return 0 # fix this later, for now don't even try
            from twisted.internet import reactor
            listener = reactor.listenTCP(portToBind, 
                            forwarding.SSHListenForwardingFactory(self,
                                (hostToBind, portToBind),
                                forwarding.SSHListenServerForwardingChannel), 
                            interface = hostToBind)
            self.listeners[(hostToBind, portToBind)] = listener
            if portToBind == 0:
                portToBind = listener.getHost()[2] # the port
                return 1, struct.pack('>L', portToBind)
            else:
                return 1
        elif requestType == 'cancel-tcpip-forward':
            hostToBind, portToBind = forwarding.unpackGlobal_tcpip_forward(data)
            listener = self.listeners.get((hostToBind, portToBind), None)
            if not listener:
                return 0
            del self.listeners[(hostToBind, portToBind)]
            listener.stopListening()
            return 1
        else:
            log.msg('ignoring unknown global request %s'%requestType)
            return 0

class SSHChannel:
    name = None # only needed for client channels
    def __init__(self, localWindow = 0, localMaxPacket = 0, 
                       remoteWindow = 0, remoteMaxPacket = 0, 
                       conn = None):
        self.localWindowSize = localWindow or 131072
        self.localWindowLeft = self.localWindowSize
        self.localMaxPacket = localMaxPacket or 32768
        self.remoteWindowLeft = remoteWindow
        self.remoteMaxPacket = remoteMaxPacket
        self.conn = conn
        self.specificData = ''
        self.buf = ''

    def channelOpen(self, specificData):
        log.msg('channel %s open'%self.id)

    def openFailed(self, reason):
        log.msg('other side refused channel %s\nreason: %s'%(self.id, reason))

    def addWindowBytes(self, bytes):
        self.remoteWindowLeft = self.remoteWindowLeft+bytes
        if self.buf:
            self.write('')

    def requestReceived(self, requestType, data):
        foo = requestType.replace('-', '_')
        f = getattr(self, 'request_%s'%foo, None)
        if f:
            return f(data)
        log.msg('unhandled request for %s'%requestType)
        return 0

    def dataReceived(self, data):
        log.msg('got data %s'%repr(data))

    def extReceived(self, dataType, data):
        log.msg('got extended data %s %s'%(dataType, repr(data)))

    def eofReceived(self):
        log.msg('channel %s remote eof'%self.id)

    def closed(self):
        log.msg('channel %s closed'%self.id)

    # transport stuff
    def write(self, data):
        if self.buf:
            data+=self.buf
            self.buf = ''
        if len(data) > self.remoteWindowLeft:
            data, self.buf = data[: self.remoteWindowLeft],  \
                            data[self.remoteWindowLeft:]
        if not data: return
        while len(data) > self.remoteMaxPacket:
            self.conn.sendData(self, data[: self.remoteMaxPacket])
            data = data[self.remoteMaxPacket:]
            self.remoteWindowLeft-=self.remoteMaxPacket
        if data:
            self.conn.sendData(self, data)
        self.remoteWindowLeft-=len(data)

    def writeSequence(self, data):
        self.write(''.join(data))

    def loseConnection(self):
        self.conn.sendClose(self)

    def getPeer(self):
        return('SSH', )+self.conn.transport.getPeer()

    def getHost(self):
        return('SSH', )+self.conn.transport.getHost()

MSG_GLOBAL_REQUEST = 80
MSG_REQUEST_SUCCESS = 81
MSG_REQUEST_FAILURE = 82
MSG_CHANNEL_OPEN = 90
MSG_CHANNEL_OPEN_CONFIRMATION = 91
MSG_CHANNEL_OPEN_FAILURE = 92
MSG_CHANNEL_WINDOW_ADJUST = 93
MSG_CHANNEL_DATA = 94
MSG_CHANNEL_EXTENDED_DATA = 95
MSG_CHANNEL_EOF = 96
MSG_CHANNEL_CLOSE = 97
MSG_CHANNEL_REQUEST = 98
MSG_CHANNEL_SUCCESS = 99
MSG_CHANNEL_FAILURE = 100

OPEN_ADMINISTRATIVELY_PROHIBITED = 1
OPEN_CONNECT_FAILED = 2
OPEN_UNKNOWN_CHANNEL_TYPE = 3
OPEN_RESOURCE_SHORTAGE = 4

EXTENDED_DATA_STDERR = 1

messages = {}
import connection
for v in dir(connection):
    if v[: 4] == 'MSG_':
        messages[getattr(connection, v)] = v # doesn't handle doubles

SSHConnection.protocolMessages = messages

from session import SSHSession # evil circular import
import forwarding
