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

    def serviceStopped(self):
        for channel in self.channels.values():
            channel.closed()

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
        """
        Send a global request for this connection.  Current this is only used
        for remote->local TCP forwarding.

        @type request:      C{str}
        @type data:         C{str}
        @type wantReply:    C{bool}
        @rtype              C{Deferred}/C{None}
        """
        self.transport.sendPacket(MSG_GLOBAL_REQUEST,
                                  common.NS(request)
                                  + (wantReply and '\xff' or '\x00')
                                  + data)
        if wantReply:
            d = defer.Deferred()
            self.deferreds.setdefault('global', []).append(d)
            return d

    def openChannel(self, channel, extra = ''):
        """
        Open a new channel on this connection.

        @type channel:  subclass of C{SSHChannel}
        @type extra:    C{str}
        """
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
        """
        Send a request to a channel.

        @type channel:      subclass of C{SSHChannel}
        @type requestType:  C{str}
        @type data:         C{str}
        @type wantReply:    C{bool}
        @rtype              C{Deferred}/C{None}
        """
        if not self.channelsToRemoteChannel.has_key(channel):
            return
        log.logOwner.own(self.transport.transport)
        log.msg('sending request for channel %s, request %s'%(channel.id, requestType))
        log.logOwner.disown(self.transport.transport)
        self.transport.sendPacket(MSG_CHANNEL_REQUEST, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel])
                                  + common.NS(requestType)+chr(wantReply)
                                  + data)
        if wantReply:
            d = defer.Deferred()
            self.deferreds.setdefault(channel.id, []).append(d)
            return d

    def adjustWindow(self, channel, bytesToAdd):
        """
        Tell the other side that we will receive more data.  This should not
        normally need to be called as it is managed automatically.

        @type channel:      subclass of C{SSHChannel}
        @type bytesToAdd:   C{int}
        """
        if not self.channelsToRemoteChannel.has_key(channel):
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_WINDOW_ADJUST, struct.pack('>2L', 
                                    self.channelsToRemoteChannel[channel], 
                                    bytesToAdd))
        channel.localWindowLeft+=bytesToAdd

    def sendData(self, channel, data):
        """
        Send data to a channel.  This should not normally be used: instead use
        channel.write(data) as it manages the window automatically.

        @type channel:  subclass of C{SSHChannel}
        @type data:     C{str}
        """
        if not self.channelsToRemoteChannel.has_key(channel):
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel])+ \
                                   common.NS(data))

    def sendExtendedData(self, channel, dataType, data):
        """
        Send extended data to a channel.  This should not normally be used:
        instead use channel.writeExtendedData(data, dataType) as it manages
        the window automatically.

        @type channel:  subclass of C{SSHChannel}
        @type dataType: C{int}
        @type data:     C{str}
        """
        if not self.channelsToRemoteChannel.has_key(channel):
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>2L', 
                            self.channelsToRemoteChannel[channel],dataType) \
                            + common.NS(data))

    def sendEOF(self, channel):
        """
        Send an EOF (End of File) for a channel.

        @type channel:  subclass of C{SSHChannel}
        """
        if not self.channelsToRemoteChannel.has_key(channel):
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_EOF, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel]))

    def sendClose(self, channel):
        """
        Close a channel.

        @type channel:  subclass of C{SSHChannel}
        """
        if not self.channelsToRemoteChannel.has_key(channel):
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_CLOSE, struct.pack('>L', 
                                    self.channelsToRemoteChannel[channel]))
        del self.channelsToRemoteChannel[channel]

    # methods to override
    def getChannel(self, channelType, windowSize, maxPacket, data):
        """
        The other side requested a channel of some sort.
        channelType is the type of channel being requested,
        windowSize is the initial size of the remote window,
        maxPacket is the largest packet we should send,
        data is any other packet data (often nothing).

        We return either a subclass of SSHChannel, or a tuple of
        (errorCode, errorMessage).

        @type channelType:  C{str}
        @type windowSize:   C{int}
        @type maxPacket:    C{int}
        @type data:         C{str}
        @rtype:             subclass of C{SSHChannel}/C{tuple}
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

        @type requestType:  C{str}
        @type data:         C{str}
        @rtype:             C{int}/C{tuple}
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
        self.extBuf = ''

    def channelOpen(self, specificData):
        """
        Called when the channel is opened.  specificData is any data that the
        other side sent us when opening the channel.

        @type specificData: C{str}
        """
        log.msg('channel %s open'%self.id)

    def openFailed(self, reason):
        """
        Called when the the open failed for some reason.
        reason.desc is a string descrption, reason.code the the SSH error code.

        @type reason: C{error.ConchError}
        """
        log.msg('other side refused channel %s\nreason: %s'%(self.id, reason))

    def addWindowBytes(self, bytes):
        """
        Called when bytes are added to the remote window.  By default it clears
        the data buffers.

        @type bytes:    C{int}
        """
        self.remoteWindowLeft = self.remoteWindowLeft+bytes
        if self.buf:
            b = self.buf
            self.buf = ''
            self.write(b)
        if self.extBuf:
            b = self.extBuf
            self.extBuf = None
            map(self.writeExtended, b)

    def requestReceived(self, requestType, data):
        """
        Called when a request is sent to this channel.  By default it delegates
        to self.request_<requestType>.
        If this functio returns true, the request succeeded, otherwise it
        failed.

        @type requestType:  C{str}
        @type data:         C{str}
        @rtype:             C{bool}
        """
        foo = requestType.replace('-', '_')
        f = getattr(self, 'request_%s'%foo, None)
        if f:
            return f(data)
        log.msg('unhandled request for %s'%requestType)
        return 0

    def dataReceived(self, data):
        """
        Called when we receive data.

        @type data: C{str}
        """
        log.msg('got data %s'%repr(data))

    def extReceived(self, dataType, data):
        """
        Called when we receive extended data (usually standard error).

        @type dataType: C{int}
        @type data:     C{str}
        """
        log.msg('got extended data %s %s'%(dataType, repr(data)))

    def eofReceived(self):
        """
        Called when the other side will send no more data.
        """
        log.msg('channel %s remote eof'%self.id)

    def closed(self):
        """
        Called when the channel is closed.
        """
        log.msg('channel %s closed'%self.id)

    # transport stuff
    def write(self, data):
        """
        Write some data to the channel.  If there is not enough remote window
        available, buffer until it is.

        @type data: C{str}
        """
        if self.buf:
            self.buf += data
            return
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

    def writeExtended(self, dataType, data):
        """
        Send extended data to this channel.  If there is not enough remote
        window available, buffer until there is.

        @type dataType: C{int}
        @type data:     C{str}
        """
        if self.extBuf:
            if self.extBuf[-1][0] == dataType:
                self.extBuf[-1][1]+=data
            else:
                self.extBuf.append((dataType, data))
            return
        if len(data) > self.remoteWindowLeft:
            data, self.extBuf = data[:self.remoteWindowLeft], \
                                [(dataType, data[self.remoteWindowLeft:])]
        if not data: return
        while len(data) > self.remoteMaxPacket:
            self.conn.sendExtendedData(self, extType, 
                                             data[:self.remoteMaxPacket])
            data = data[self.remoteMaxPacket:]
            self.remoteWindowLeft-=self.remoteMaxPacket
        if data:
            self.conn.sendExtendedData(self, extType, data)
            self.remoteWindowLeft-=len(data)

    def writeSequence(self, data):
        """
        Part of the Transport interface.  Write a list of strings to the
        channel.

        @type data: C{list} of C{str}
        """
        self.write(''.join(data))

    def loseConnection(self):
        """
        Close the channel.
        """
        self.conn.sendClose(self)

    def getPeer(self):
        """
        Return a tuple describing the other side of the connection.

        @rtype: C{tuple}
        """
        return('SSH', )+self.conn.transport.getPeer()

    def getHost(self):
        """
        Return a tuple describing out side of the connection.

        @rtype: C{tuple}
        """
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
