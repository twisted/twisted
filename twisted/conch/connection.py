import struct
from twisted.internet import protocol, ptypro
import service, common

class SSHConnection(service.SSHService):
    name = 'ssh-connection'
    localChannelID = 0
    localToRemoteChannel = {}
    channels = {}
    channelsToRemoteChannel = {}
    
    def ssh_CHANNEL_OPEN(self, packet):
        channelType, rest = common.getNS(packet)
        senderChannel, windowSize, maxPacket = struct.unpack('>3L', rest[:12])
        packet = rest[12:]
        channel = self.getChannel(channelType, windowSize, maxPacket, packet)
        if type(channel)!=type((1,)):
            localChannel = self.localChannelID
            self.localChannelID += 1
            self.channels[localChannel] = channel
            self.channelsToRemoteChannel[channel] = senderChannel
            self.localToRemoteChannel[localChannel] = senderChannel
            self.transport.sendPacket(MSG_CHANNEL_OPEN_CONFIRMATION, struct.pack('>4L',
                                        senderChannel, localChannel, windowSize, maxPacket) +\
                                      channel.specificData)
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
        self.channels[localChannel].receiveData(data)

    def ssh_CHANNEL_EXTENDED_DATA(self, packet):
        localChannel, typeCode = struct.unpack('>2L', packet[:8])
        data = common.getNS(packet[8:])[0]
        self.channels[localChannel].receiveExtendedData(typeCode, data)

    def ssh_CHANNEL_EOF(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        self.channels[localChannel].receiveEOF()

    def ssh_CHANNEL_CLOSE(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        self.channels[localChannel].receiveClose()
        del self.localToRemoteChannel[localChannel]
        del self.channels[localChannel]

    def ssh_CHANNEL_REQUEST(self, packet):
        localChannel = struct.unpack('>L', packet[:4])[0]
        requestType, rest = common.getNS(packet[4:])
        wantReply = ord(rest[0])
        if self.channels[localChannel].receiveRequest(requestType, rest[1:]):
            reply = MSG_CHANNEL_SUCCESS
        else:
            reply = MSG_CHANNEL_FAILURE
        if wantReply:
            self.transport.sendPacket(reply, struct.pack('>L', self.localToRemoteChannel[localChannel]))

    def openChannel(self, channel, extra = ''):
        self.transport.sendPacket(MSG_CHANNEL_OPEN, common.NS(channel.name) 
                + struct.pack('>3L', self.localChannelID,
                              channel.windowSize, channel.maxPacket)
                + extra)
        self.channels[self.localChannelID] = channel
        self.localChannelID += 1

    def sendRequest(self, channel, requestType, data, wantReply = 0):
        # XXX handle wantReply
        self.transport.sendPacket(MSG_CHANNEL_REQUEST, struct.pack('>L',
                                            self.channelsToRemoteChannel[channel]) + \
                                            common.NS(requestType)+chr(wantReply) + \
                                            data)
        
    def sendData(self, channel, data):
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>L',
                                            self.channelsToRemoteChannel[channel]) + \
                                            common.NS(data))

    def sendExtendedData(self, channel, dataType, data):
        self.transport.sendPacket(MSG_CHANNEL_DATA, struct.pack('>2L',
                                            self.channelsToRemoteChannel[channel]), dataType + \
                                            common.NS(data))

    def sendClose(self, channel):
        if channel not in self.channels.values():
            return # we're already closed
        self.transport.sendPacket(MSG_CHANNEL_CLOSE, struct.pack('>L',
                                            self.channelsToRemoteChannel[channel]))        
        del self.channelsToRemoteChannel[channel]

    def getChannel(self, channelType, windowSize, maxPacket, packet):
        if not hasattr(self.transport, 'factory'):
            return OPEN_ADMINISTRATIVELY_PROHIBITED, 'not on the client bubba'
        if channelType == 'session':
            return SSHSession(windowSize, maxPacket, self)
        return OPEN_UNKNOWN_CHANNEL_TYPE, "don't know %s" % channelTypes

class SSHChannel:
    name = None # only needed for client channels
    def __init__(self, window, maxPacket, conn = None):
        self.conn = conn
        self.windowSize = window
        self.windowLeft = window
        self.maxPacket = maxPacket
        self.specificData = ''

    def channelOpen(self):
        print 'channel open'

    def addWindowBytes(self, bytes):
        self.windowSize = self.windowSize + bytes
        self.windowLeft = self.windowLeft + bytes

    def receiveRequest(self, requestType, data):
        print 'got request', requestType, repr(data)

    def receiveData(self, data):
        print 'got data', repr(data)

    def receiveExtendedData(self, dataType, data):
        print 'got extended data', dataType, repr(data)

    def receiveEOF(self):
        print 'got eof'

    def receiveClose(self):
        print 'closed'

class SSHSession(SSHChannel, protocol.Protocol): # treat us as a protocol for the sake of Process
    environ = {}
    def receiveRequest(self, requestType, data):
        if requestType == 'subsystem':
            subsystem = common.getNS(data)[0]
            print 'accepted subsystem', subsystem
            return 1
        elif requestType == 'shell':
            shell = '/bin/sh' # fix this
            print 'accepted shell', shell
            ptypro.Process(shell, [shell], self.environ, '/tmp', self) # fix this too
            return 1
        elif requestType == 'exec':
            print 'disabled exec'
            return 0
            print 'accepted exec (horribly insecure)', data[4:]
            args = data[4:].split()
            ptypro.Process(args[0], args, self.environ, '/tmp', self)
            return 1
        elif requestType == 'pty-req':
            term, rest = common.getNS(data)
            cols, rows, foo, bar = struct.unpack('>4L', rest[:16])
            modes = common.getNS(rest[16:])[0]
            self.environ['TERM'] = term
            self.environ['ROWS'] = str(rows)
            self.environ['COLUMNS'] = str(cols)
            # XXX handle modes
            print repr(modes)
            return 1
        else:
            print 'got request', requestType, repr(data)

    def receiveData(self, data):
        self.transport.write(data)

    # protocol stuff
    def dataReceived(self, data):
        self.conn.sendData(self, data)

    def errReceived(self, err):
        self.conn.sendExtendedData(self, EXTENDED_DATA_STDERR, err)

    def processEnded(self):
        self.conn.sendClose(self)

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
