# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""
Implements the old SSHv1 key agent protocol.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import struct
from common import NS, getNS
from twisted.conch.error import ConchError
from twisted.internet import defer, protocol

class SSHAgentClient(protocol.Protocol):
    
    def __init__(self):
        self.buf = ''
        self.deferreds = []

    def dataReceived(self, data):
        self.buf += data
        while 1:
            if len(self.buf) <= 4: return
            packLen = struct.unpack('!L', self.buf[:4])[0]
            if len(self.buf) < 4+packLen: return
            packet, self.buf = self.buf[4:4+packLen], self.buf[4+packLen:]
            reqType = ord(packet[0])
            d = self.deferreds.pop(0)
            if reqType == AGENT_FAILURE:
                d.errback(ConchError('agent failure'))
            elif reqType == AGENT_SUCCESS:
                d.callback('')
            else:
                d.callback(packet)

    def sendRequest(self, reqType, data):
        pack = struct.pack('!LB',len(data)+1, reqType)+data
        self.transport.write(pack)
        d = defer.Deferred()
        self.deferreds.append(d)
        return d

    def requestIdentities(self):
        return self.sendRequest(AGENTC_REQUEST_IDENTITIES, '').addCallback(self._cbRequestIdentities)

    def _cbRequestIdentities(self, data):
        if ord(data[0]) != AGENT_IDENTITIES_ANSWER:
            return ConchError('unexpected respone: %i' % ord(data[0]))
        numKeys = struct.unpack('!L', data[1:5])[0]
        keys = []
        data = data[5:]
        for i in range(numKeys):
            blobLen = struct.unpack('!L', data[:4])[0]
            blob, data = data[4:4+blobLen], data[4+blobLen:]
            commLen = struct.unpack('!L', data[:4])[0]
            comm, data = data[4:4+commLen], data[4+commLen:]
            keys.append((blob, comm))
        return keys

    def addIdentity(self, blob, comment = ''):
        req = blob
        req += NS(comment)
        co
        return self.sendRequest(AGENTC_ADD_IDENTITY, req)

    def signData(self, blob, data):
        req = NS(blob)
        req += NS(data)
        req += '\000\000\000\000' # flags
        return self.sendRequest(AGENTC_SIGN_REQUEST, req).addCallback(self._cbSignData)

    def _cbSignData(self, data):
        if data[0] != chr(AGENT_SIGN_RESPONSE):
            return ConchError('unexpected data: %i' % ord(data[0]))
        signature = getNS(data[1:])[0]
        return signature

    def removeIdentity(self, blob):
        req = NS(blob)
        return self.sendRequest(AGENTC_REMOVE_IDENTITY, req)

    def removeAllIdentities(self):
        return self.sendRequest(AGENTC_REMOVE_ALL_IDENTITIES, '')

class SSHAgentServer(protocol.Protocol):

    def __init__(self):
        self.buf = '' 

    def dataReceived(self, data):
        self.buf += data
        while 1:
            if len(self.buf) <= 4: return
            packLen = struct.unpack('!L', self.buf[:4])[0]
            if len(self.buf) < 4+packLen: return
            packet, self.buf = self.buf[4:4+packLen], self.buf[4+packLen:]
            reqType = ord(packet[0])
            reqName = messages.get(reqType, None)
            if not reqName:
                print 'bad request', reqType
            f = getattr(self, 'agentc_%s' % reqName)
            f(packet[1:])

    def sendResponse(self, reqType, data):
        pack = struct.pack('!LB', len(data)+1, reqType) + data
        self.transport.write(pack)

    def agentc_REQUEST_IDENTITIES(self, data):
        assert data == ''
        numKeys = len(self.keys)
        s = struct.pack('!L', numKeys)
        for k in self.keys:
            s += struct.pack('!L', len(k)) + k
            s += struct.pack('!L', len(self.keys[k][1])) + self.keys[k][1]
        self.sendResponse(AGENT_IDENTITIES_ANSWER, s)

    def agentc_SIGN_REQUEST(self, data):
        blob, data = common.getNS(data)
        if blob not in self.keys:
            return self.sendResponse(AGENT_FAILURE, '')
        signData, data = common.getNS(data)
        assert data == '\000\000\000\000'
        self.sendResponse(AGENT_SIGN_RESPONSE, common.NS(keys.signData(self.keys[blob][0], signData)))

    def agentc_ADD_IDENTITY(self, data): pass
    def agentc_REMOVE_IDENTITY(self, data): pass
    def agentc_REMOVE_ALL_IDENTITIES(self, data): pass

AGENT_FAILURE                   = 5
AGENT_SUCCESS                   = 6
AGENTC_REQUEST_IDENTITIES       = 11
AGENT_IDENTITIES_ANSWER         = 12
AGENTC_SIGN_REQUEST             = 13
AGENT_SIGN_RESPONSE             = 14
AGENTC_ADD_IDENTITY             = 17
AGENTC_REMOVE_IDENTITY          = 18
AGENTC_REMOVE_ALL_IDENTITIES    = 19

messages = {}
import agent
for v in dir(agent):
    if v.startswith('AGENTC_'):
        messages[getattr(agent, v)] = v[7:]
