# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

from twisted.conch.error import ConchError
from twisted.conch.ssh import channel, connection
from twisted.internet import defer, protocol, reactor
from twisted.python import log
from twisted.spread import banana

import os, stat, pickle
import types # this is for evil

class SSHUnixClientFactory(protocol.ClientFactory):
#    noisy = 1

    def __init__(self, d, options, userAuthObject):
        self.d = d
        self.options = options
        self.userAuthObject = userAuthObject
        
    def clientConnectionLost(self, connector, reason):
        if self.options['reconnect']:
            connector.connect()
        #log.err(reason)
        if not self.d: return
        d = self.d
        self.d = None
        d.errback(reason)
      

    def clientConnectionFailed(self, connector, reason):
        #try:
        #    os.unlink(connector.transport.addr)
        #except:
        #    pass
        #log.err(reason)
        if not self.d: return
        d = self.d
        self.d = None
        d.errback(reason)
       #reactor.connectTCP(options['host'], options['port'], SSHClientFactory())
    
    def startedConnecting(self, connector):
        fd = connector.transport.fileno()
        stats = os.fstat(fd)
        try:
            filestats = os.stat(connector.transport.addr)
        except:
            connector.stopConnecting()
            return
        if stat.S_IMODE(filestats[0]) != 0600:
            log.msg("socket mode is not 0600: %s" % oct(stat.S_IMODE(stats[0])))
        elif filestats[4] != os.getuid():
            log.msg("socket not owned by us: %s" % stats[4])
        elif filestats[5] != os.getgid():
            log.msg("socket not owned by our group: %s" % stats[5])
        # XXX reenable this when i can fix it for cygwin
        #elif filestats[-3:] != stats[-3:]:
        #    log.msg("socket doesn't have same create times")
        else:
            log.msg('conecting OK')
            return
        connector.stopConnecting()

    def buildProtocol(self, addr):
        # here comes the EVIL
        obj = self.userAuthObject.instance
        bases = []
        for base in obj.__class__.__bases__:
            if base == connection.SSHConnection:
                bases.append(SSHUnixClientProtocol)
            else:
                bases.append(base)
        newClass = types.ClassType(obj.__class__.__name__, tuple(bases), obj.__class__.__dict__)
        obj.__class__ = newClass
        SSHUnixClientProtocol.__init__(obj)
        log.msg('returning %s' % obj)
        if self.d:
            d = self.d
            self.d = None
            d.callback(None)
        return obj

class SSHUnixServerFactory(protocol.Factory):
    def __init__(self, conn):
        self.conn = conn

    def buildProtocol(self, addr):
        return SSHUnixServerProtocol(self.conn)

class SSHUnixProtocol(banana.Banana):

    knownDialects = ['none']

    def __init__(self):
        banana.Banana.__init__(self)
        self.deferredQueue = []
        self.deferreds = {}
        self.deferredID = 0

    def connectionMade(self):
        log.msg('connection made %s' % self)
        banana.Banana.connectionMade(self)

    def expressionReceived(self, lst):
        vocabName = lst[0]
        fn = "msg_%s" % vocabName
        func = getattr(self, fn)
        func(lst[1:])

    def sendMessage(self, vocabName, *tup):
        self.sendEncoded([vocabName] + list(tup))

    def returnDeferredLocal(self):
        d = defer.Deferred()
        self.deferredQueue.append(d)
        return d

    def returnDeferredWire(self, d):
        di = self.deferredID
        self.deferredID += 1
        self.sendMessage('returnDeferred', di)
        d.addCallback(self._cbDeferred, di)
        d.addErrback(self._ebDeferred, di)

    def _cbDeferred(self, result, di):
        self.sendMessage('callbackDeferred', di, pickle.dumps(result))

    def _ebDeferred(self, reason, di):
        self.sendMessage('errbackDeferred', di, pickle.dumps(reason))

    def msg_returnDeferred(self, lst):
        deferredID = lst[0]
        self.deferreds[deferredID] = self.deferredQueue.pop(0)

    def msg_callbackDeferred(self, lst):
        deferredID, result = lst
        d = self.deferreds[deferredID]
        del self.deferreds[deferredID]
        d.callback(pickle.loads(result))

    def msg_errbackDeferred(self, lst):
        deferredID, result = lst
        d = self.deferreds[deferredID]
        del self.deferreds[deferredID]
        d.errback(pickle.loads(result))

class SSHUnixClientProtocol(SSHUnixProtocol):

    def __init__(self):
        SSHUnixProtocol.__init__(self)
        self.isClient = 1
        self.channelQueue = []
        self.channels = {}

    def logPrefix(self):
        return "SSHUnixClientProtocol (%i) on %s" % (id(self), self.transport.logPrefix())

    def connectionReady(self):
        log.msg('connection ready')
        self.serviceStarted()

    def connectionLost(self, reason):
        self.serviceStopped()

    def requestRemoteForwarding(self, remotePort, hostport):
        self.sendMessage('requestRemoteForwarding', remotePort, hostport)

    def cancelRemoteForwarding(self, remotePort):
        self.sendMessage('cancelRemoteForwarding', remotePort)

    def sendGlobalRequest(self, request, data, wantReply = 0):
        self.sendMessage('sendGlobalRequest', request, data, wantReply)
        if wantReply:
            return self.returnDeferredLocal()

    def openChannel(self, channel, extra = ''):
        self.channelQueue.append(channel)
        channel.conn = self
        self.sendMessage('openChannel', channel.name,
                                        channel.localWindowSize,
                                        channel.localMaxPacket, extra)

    def sendRequest(self, channel, requestType, data, wantReply = 0):
        self.sendMessage('sendRequest', channel.id, requestType, data, wantReply)
        if wantReply:
            return self.returnDeferredLocal()

    def adjustWindow(self, channel, bytesToAdd):
        self.sendMessage('adjustWindow', channel.id, bytesToAdd)

    def sendData(self, channel, data):
        self.sendMessage('sendData', channel.id, data)

    def sendExtendedData(self, channel, dataType, data):
        self.sendMessage('sendExtendedData', channel.id, data)

    def sendEOF(self, channel):
        self.sendMessage('sendEOF', channel.id)

    def sendClose(self, channel):
        self.sendMessage('sendClose', channel.id)

    def msg_channelID(self, lst):
        channelID = lst[0]
        self.channels[channelID] = self.channelQueue.pop(0)
        self.channels[channelID].id = channelID

    def msg_channelOpen(self, lst):
        channelID, remoteWindow, remoteMax, specificData = lst
        channel = self.channels[channelID]
        channel.remoteWindowLeft = remoteWindow
        channel.remoteMaxPacket = remoteMax
        channel.channelOpen(specificData)

    def msg_openFailed(self, lst):
        channelID, reason = lst
        self.channels[channelID].openFailed(pickle.loads(reason))
        del self.channels[channelID]

    def msg_addWindowBytes(self, lst):
        channelID, bytes = lst
        self.channels[channelID].addWindowBytes(bytes)

    def msg_requestReceived(self, lst):
        channelID, requestType, data = lst
        d = defer.maybeDeferred(self.channels[channelID].requestReceived, requestType, data)
        self.returnDeferredWire(d)

    def msg_dataReceived(self, lst):
        channelID, data = lst
        self.channels[channelID].dataReceived(data)

    def msg_extReceived(self, lst):
        channelID, dataType, data = lst
        self.channels[channelID].extReceived(dataType, data)

    def msg_eofReceived(self, lst):
        channelID = lst[0]
        self.channels[channelID].eofReceived()

    def msg_closeReceived(self, lst):
        channelID = lst[0]
        channel = self.channels[channelID]
        channel.remoteClosed = 1
        channel.closeReceived()

    def msg_closed(self, lst):
        channelID = lst[0]
        channel = self.channels[channelID]
        self.channelClosed(channel)

    def channelClosed(self, channel):
        channel.localClosed = channel.remoteClosed = 1
        del self.channels[channel.id]
        log.callWithLogger(channel, channel.closed)

    # just in case the user doesn't override
    
    def serviceStarted(self):
        pass

    def serviceStopped(self):
        pass

class SSHUnixServerProtocol(SSHUnixProtocol):

    def __init__(self, conn):
        SSHUnixProtocol.__init__(self)
        self.isClient = 0
        self.conn = conn

    def connectionLost(self, reason):
        for channel in self.conn.channels.values():
            if isinstance(channel, SSHUnixChannel) and channel.unix == self:
                log.msg('forcibly closing %s' % channel)
                try:
                    self.conn.sendClose(channel)
                except:
                    pass

    def haveChannel(self, channelID):
        return self.conn.channels.has_key(channelID)

    def getChannel(self, channelID):
        channel = self.conn.channels[channelID]
        if not isinstance(channel, SSHUnixChannel):
            raise ConchError('nice try bub')
        return channel

    def msg_requestRemoteForwarding(self, lst):
        remotePort, hostport = lst
        hostport = tuple(hostport)
        self.conn.requestRemoteForwarding(remotePort, hostport)

    def msg_cancelRemoteForwarding(self, lst):
        [remotePort] = lst
        self.conn.cancelRemoteForwarding(remotePort)

    def msg_sendGlobalRequest(self, lst):
        requestName, data, wantReply = lst
        d = self.conn.sendGlobalRequest(requestName, data, wantReply)
        if wantReply:
            self.returnDeferredWire(d)

    def msg_openChannel(self, lst):
        name, windowSize, maxPacket, extra = lst
        channel = SSHUnixChannel(self, name, windowSize, maxPacket)
        self.conn.openChannel(channel, extra)
        self.sendMessage('channelID', channel.id)

    def msg_sendRequest(self, lst):
        cn, requestType, data, wantReply = lst
        if not self.haveChannel(cn):
            if wantReply:
                self.returnDeferredWire(defer.fail(ConchError("no channel")))
        channel = self.getChannel(cn)
        d = self.conn.sendRequest(channel, requestType, data, wantReply)
        if wantReply:
            self.returnDeferredWire(d)

    def msg_adjustWindow(self, lst):
        cn, bytesToAdd = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        self.conn.adjustWindow(channel, bytesToAdd)

    def msg_sendData(self, lst):
        cn, data = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        self.conn.sendData(channel, data)

    def msg_sendExtended(self, lst):
        cn, dataType, data = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        self.conn.sendExtendedData(channel, dataType, data)

    def msg_sendEOF(self, lst):
        (cn, ) = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        self.conn.sendEOF(channel)

    def msg_sendClose(self, lst):
        (cn, ) = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        self.conn.sendClose(channel)

class SSHUnixChannel(channel.SSHChannel):
    def __init__(self, unix, name, windowSize, maxPacket):
        channel.SSHChannel.__init__(self, windowSize, maxPacket, conn = unix.conn)
        self.unix = unix
        self.name = name

    def channelOpen(self, specificData):
        self.unix.sendMessage('channelOpen', self.id, self.remoteWindowLeft,
                                             self.remoteMaxPacket, specificData)

    def openFailed(self, reason):
        self.unix.sendMessage('openFailed', self.id, pickle.dumps(reason))

    def addWindowBytes(self, bytes):
        self.unix.sendMessage('addWindowBytes', self.id, bytes)

    def dataReceived(self, data):
        self.unix.sendMessage('dataReceived', self.id, data)

    def requestReceived(self, reqType, data):
        self.unix.sendMessage('requestReceived', self.id, reqType, data)
        return self.unix.returnDeferredLocal()

    def extReceived(self, dataType, data):
        self.unix.sendMessage('extReceived', self.id, dataType, data)

    def eofReceived(self):
        self.unix.sendMessage('eofReceived', self.id)

    def closeReceived(self):
        self.unix.sendMessage('closeReceived', self.id)

    def closed(self):
        self.unix.sendMessage('closed', self.id)

def connect(host, port, options, verifyHostKey, userAuthObject):
    if options['nocache']: 
        return defer.fail(ConchError('not using connection caching'))
    d = defer.Deferred()
    filename = os.path.expanduser("~/.conch-%s-%s-%i" % (userAuthObject.user, host, port))
    factory = SSHUnixClientFactory(d, options, userAuthObject)
    reactor.connectUNIX(filename, factory, timeout=2, checkPID=1)
    return d
