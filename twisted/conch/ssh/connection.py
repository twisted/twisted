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

"""This module contains the implementation of the ssh-connection service, which allows access to the shell and port-forwarding.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import struct
from twisted.internet import protocol, reactor, process
from twisted.python import log
from twisted.conch import error
import service, common

class SSHConnection(service.SSHService):
    name = 'ssh-connection'
    localChannelID = 0
    localToRemoteChannel = {}
    channels = {}
    channelsToRemoteChannel = {}
    deferreds = {}

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
                
    def ssh_CHANNEL_OPEN(self, packet):
        channelType, rest = common.getNS(packet)
        senderChannel, windowSize, maxPacket = struct.unpack('>3L', rest[:12])
        packet = rest[12:]
        channel = self.getChannel(channelType, windowSize, maxPacket, packet)
        if type(channel)!=type((1,)):
            localChannel = self.localChannelID
            self.localChannelID += 1
            channel.id = localChannel
            self.channels[localChannel] = channel
            self.channelsToRemoteChannel[channel] = senderChannel
            self.localToRemoteChannel[localChannel] = senderChannel
            self.transport.sendPacket(MSG_CHANNEL_OPEN_CONFIRMATION, struct.pack('>4L',
                                        senderChannel, localChannel, windowSize, maxPacket) +\
                                      channel.specificData)
            channel.channelOpen()
        else:
            reason, textualInfo = channel
            self.transport.sendPacket(MSG_CHANNEL_OPEN_FAILURE,
                                      struct.pack('>2L', senderChannel, reason) + \
                                      common.NS(textualINFO) + common.NS(''))

    def ssh_CHANNEL_OPEN_CONFIRMATION(self, packet):
        localChannel, remoteChannel, windowSize, maxPacket = struct.unpack('>4L', packet[:16])
        specificData = packet[16:]
        channel = self.channels[localChannel]
        channel.conn = self
        self.localToRemoteChannel[localChannel] = remoteChannel
        self.channelsToRemoteChannel[channel] = remoteChannel
        channel.channelOpen(specificData)

    def ssh_CHANNEL_WINDOW_ADJUST(self, packet):
        localChannel, bytesToAdd = struct.unpack('>2L', packet[:8])
        self.channels[localChannel].addWindowBytes(bytesToAdd)

    def ssh_CHANNEL_DATA(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        data = common.getNS(packet[4:])[0]
        self.channels[localChannel].dataReceived(data)

    def ssh_CHANNEL_EXTENDED_DATA(self, packet):
        localChannel, typeCode = struct.unpack('>2L', packet[:8])
        data = common.getNS(packet[8:])[0]
        self.channels[localChannel].extReceived(typeCode, data)

    def ssh_CHANNEL_EOF(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        self.channels[localChannel].eofReceived()

    def ssh_CHANNEL_CLOSE(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        channel = self.channels[localChannel]
        channel.closed()
        del self.localToRemoteChannel[localChannel]
        del self.channels[localChannel]
        try:
            del self.channelsToRemoteChannel[channel]
        except KeyError:
            pass # we'd already closed this end


    def ssh_CHANNEL_REQUEST(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        requestType, rest = common.getNS(packet[4:])
        wantReply = ord(rest[0])
        if self.channels[localChannel].requestReceived(requestType, rest[1:]):
            reply = MSG_CHANNEL_SUCCESS
        else:
            reply = MSG_CHANNEL_FAILURE
        if wantReply:
            self.transport.sendPacket(reply, struct.pack('>L', self.localToRemoteChannel[localChannel]))

    def ssh_CHANNEL_SUCCESS(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        if self.deferreds.has_key(localChannel):
            d = self.deferreds[localChannel].pop(0)
            d.callback(packet[4:])

    def ssh_CHANNEL_FAILURE(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        if self.deferreds.has_key(localChannel):
            d = self.deferreds[localChannel].pop(0)
            d.errback(ConchError('channel request failed'))

    # methods for users of the connection to call
    def openChannel(self, channel, extra = ''):
        self.transport.sendPacket(MSG_CHANNEL_OPEN, common.NS(channel.name) 
                + struct.pack('>3L', self.localChannelID,
                              channel.windowSize, channel.maxPacket)
                + extra)
        channel.id = self.localChannelID
        self.channels[self.localChannelID] = channel
        self.localChannelID += 1

    def sendRequest(self, channel, requestType, data, wantReply = 0):
        log.msg('sending request for channel %s, request %s' % (channel.id, requestType))
        
        self.transport.sendPacket(MSG_CHANNEL_REQUEST, struct.pack('>L',
                                            self.channelsToRemoteChannel[channel]) + \
                                            common.NS(requestType)+chr(wantReply) + \
                                            data)
        d = defer.Deferred()
        if not self.deferreds.has_key(channel.id):
            self.deferreds[channel.id] = []
        self.deferreds[channel.id].append(d)
        return d
        
    def sendData(self, channel, data):
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>L',
                                            self.channelsToRemoteChannel[channel]) + \
                                            common.NS(data))

    def sendExtendedData(self, channel, dataType, data):
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>2L',
                                            self.channelsToRemoteChannel[channel]), dataType + \
                                            common.NS(data))

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
        windowSize is the initial size of the window
        maxPacket is the largest size of packet this channel should send
        data is any other packet data

        either this returns something that is a subclass of SSHChannel (although
        this isn't enforced), or a tuple of errorCode, errorString.
        """
        if self.transport.isClient:
            return OPEN_ADMINISTRATIVELY_PROHIBITED, 'not on the client bubba'
        if channelType == 'session':
            return SSHSession(windowSize, maxPacket, self)
        return OPEN_UNKNOWN_CHANNEL_TYPE, "don't know %s" % channelTypes

    def gotGlobalRequest(self, requestType, data):
        """we got a global request.  pretty much, this is just used by the client
        to request that we forward a port from the server to the client.
        returns either:
            1: request accepted
            1, <data>: request accepted with request specific data
            0: request denied
        """
        return 0
        
class SSHChannel:
    name = None # only needed for client channels
    def __init__(self, window, maxPacket, conn = None):
        self.conn = conn
        self.windowSize = window
        self.windowLeft = window
        self.maxPacket = maxPacket
        self.specificData = ''

    def channelOpen(self):
        log.msg('channel %s open' % self.id)

    def openFailed(self):
        log.msg('other side refused channel %s' % self.id)

    def addWindowBytes(self, bytes):
        self.windowSize = self.windowSize + bytes
        self.windowLeft = self.windowLeft + bytes

    def requestReceived(self, requestType, data):
        foo = requestType.replace('-','_')
        f = getattr(self,'request_%s' % foo, None)
        if f:
            return f(data)
        log.msg('unhandled request for %s' % requestType)
        return 0

    def dataReceived(self, data):
        log.msg('got data %s' % repr(data))

    def extReceived(self, dataType, data):
        log.msg('got extended data %s %s' % (dataType, repr(data)))

    def eofReceived(self):
        log.msg('channel %s remote eof' % self.id)

    def closed(self):
        log.msg('channel %s closed' % self.id)

    # transport stuff
    def write(self, data):
        if len(data) > self.windowLeft:
            self.conn.adjustWindow(self, len(data))
        self.conn.sendData(self, data)

    def writeSequence(self, data):
        self.write(''.join(data))

    def loseConnection(self):
        self.conn.sendClose(self)

    def getPeer(self):
        return ('SSH',) + self.conn.transport.getPeer()

    def getHost(self):
        return ('SSH',) + self.conn.transport.getHost()

class SSHSession(SSHChannel):

    environ = {}

    def request_subsystem(self, data):
        subsystem = common.getNS(data)[0]
        f = getattr(self,'subsystem_%s' % subsystem, None)
        if f:
            log.msg('starting subsystem %s' % subsystem)
            self.client = f()
            return 1
        elif self.conn.factory.authorizer.clients.has_key(subsytem):
            # we have a client for a pb service
            pass # for now
        log.msg('failed to get subsystem %s' % subsystem)
        return 0

    def request_shell(self, data):
        if not self.environ.has_key('TERM'): # we didn't get a pty-req
            log.msg('tried to get shell without pty, failing')
            return 0
        shell = '/bin/sh' # fix this
        try:
            self.client = SSHSessionClient()
            p = reactor.spawnProcess(SSHSessionProtocol(self, self.client), \
                shell, ["-"], self.environ, '/tmp', usePTY = 1)
            p.setWindowSize(*self.winSize)
        except OSError, ImportError:
            log.msg('failed to get pty')
            return 0
        else:
            log.msg('starting shell %s' % shell)
            return 1

    def request_exec(self, data):
        log.msg('disabled exec')
        return 0

    def request_pty_req(self, data):
        term, rest = common.getNS(data)
        cols, rows, xpixel, ypixel = struct.unpack('>4L', rest[:16])
        modes = common.getNS(rest[16:])[0]
        self.environ['TERM'] = term
        self.winSize = (rows, cols, xpixel, ypixel)
# XXX handle modes
        return 1

    def subsystem_python(self):
        # XXX hack hack hack
        # this should be refacted into the 'interface to pb service' part
        from twisted.manhole import telnet
        pyshell = telnet.Shell()
        pyshell.connectionMade = lambda *args: None
        pyshell.lineBuffer = []
        self.namespace = {
            'session':self,
            'connection':self.conn,
            'transport':self.conn.transport,
        }
        pyshell.factory = self # we need pyshell.factory.namespace
        pyshell.delimiters.append('\n')
        pyshell.mode = 'Command'
        pyshell.makeConnection(self) # because we're the transport
        pyshell.loggedIn() # since we've logged in by the time we make it here
        self.receiveEOF = self.loseConnection
        return pyshell

    def dataReceived(self, data):
        if not hasattr(self, 'client'):
            log.msg("hmm, got data, but we don't have a client: %s" % repr(data))
            self.conn.sendClose(self)
            return
        self.client.dataReceived(data)

    def extReceived(self, dataType, data):
        if dataType == EXTENDED_DATA_STDERR:
            if hasattr(self.client, 'errReceieved'):
                self.client.errReceived(data)
        else:
            log.msg('weird extended data: %s' % dataType)

#    def receiveEOF(self):
#        pass # don't know what to do with this

    def closed(self):
        try:
            del self.client
        except AttributeError:
            pass # we didn't have a client
        SSHChannel.closed(self)

class SSHSessionProtocol(protocol.Protocol, protocol.ProcessProtocol):
    def __init__(self, session, client):
        self.session = session
        self.client = client

    def connectionMade(self):
        print self.transport
        self.client.transport = self.transport

    def dataReceived(self, data):
        self.session.write(data)

    outReceived = dataReceived

    def errReceived(self, err):
        self.session.conn.sendExtendedData(self.session, EXTENDED_DATA_STDERR, err)

    def connectionLost(self, reason = None):
        self.session.loseConnection()

    def processEnded(self, reason = None):
        if reason and hasattr(reason, 'exitCode'): self.session.conn.sendRequest(self.session, 'exit-status', struct.pack('!L', reason.exitCode))
        self.session.loseConnection()

class SSHSessionClient:

    def dataReceived(self, data):
        self.transport.write(data)

MSG_GLOBAL_REQUEST                = 80
MSG_REQUEST_SUCCESS               = 81
MSG_REQUEST_FAILURE               = 82
MSG_CHANNEL_OPEN                  = 90
MSG_CHANNEL_OPEN_CONFIRMATION     = 91
MSG_CHANNEL_OPEN_FAILURE          = 92
MSG_CHANNEL_WINDOW_ADJUST         = 93
MSG_CHANNEL_DATA                  = 94
MSG_CHANNEL_EXTENDED_DATA         = 95
MSG_CHANNEL_EOF                   = 96
MSG_CHANNEL_CLOSE                 = 97
MSG_CHANNEL_REQUEST               = 98
MSG_CHANNEL_SUCCESS               = 99
MSG_CHANNEL_FAILURE               = 100

OPEN_ADMINISTRATIVELY_PROHIBITED  = 1
OPEN_CONNECT_FAILED               = 2
OPEN_UNKNOWN_CHANNEL_TYPE         = 3
OPEN_RESOURCE_SHORTAGE            = 4

EXTENDED_DATA_STDERR              = 1

messages = {}
import connection
for v in dir(connection):
    if v[:4]=='MSG_':
        messages[getattr(connection,v)] = v # doesn't handle doubles

SSHConnection.protocolMessages = messages

