# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""
Implements the old SSHv1 key agent protocol.

Maintainer: Paul Swartz
"""

import struct
from common import NS, getNS
from twisted.conch.error import ConchError
from twisted.conch.ssh import keys
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
            raise ConchError('unexpected respone: %i' % ord(data[0]))
        numKeys = struct.unpack('!L', data[1:5])[0]
        keys = []
        data = data[5:]
        for i in range(numKeys):
            blob, data = getNS(data)
            comment, data = getNS(data)
            keys.append((blob, comment))
        return keys

    def addIdentity(self, blob, comment = ''):
        req = blob
        req += NS(comment)
        return self.sendRequest(AGENTC_ADD_IDENTITY, req)

    def signData(self, blob, data):
        req = NS(blob)
        req += NS(data)
        req += '\000\000\000\000' # flags
        return self.sendRequest(AGENTC_SIGN_REQUEST, req).addCallback(self._cbSignData)

    def _cbSignData(self, data):
        if ord(data[0]) != AGENT_SIGN_RESPONSE:
            raise ConchError('unexpected data: %i' % ord(data[0]))
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
                self.sendResponse(AGENT_FAILURE, '')
            else:
                f = getattr(self, 'agentc_%s' % reqName)
                if not hasattr(self.factory, 'keys'):
                    self.factory.keys = {}
                f(packet[1:])

    def sendResponse(self, reqType, data):
        pack = struct.pack('!LB', len(data)+1, reqType) + data
        self.transport.write(pack)

    def agentc_REQUEST_IDENTITIES(self, data):
        assert data == ''
        numKeys = len(self.factory.keys)
        s = struct.pack('!L', numKeys)
        for key, comment in self.factory.keys.itervalues():
            s += NS(key.blob()) # yes, wrapped in an NS
            s += NS(comment)
        self.sendResponse(AGENT_IDENTITIES_ANSWER, s)

    def agentc_SIGN_REQUEST(self, data):
        blob, data = getNS(data)
        if blob not in self.factory.keys:
            return self.sendResponse(AGENT_FAILURE, '')
        signData, data = getNS(data)
        assert data == '\000\000\000\000'
        self.sendResponse(AGENT_SIGN_RESPONSE, NS(self.factory.keys[blob][0].sign(signData)))

    def agentc_ADD_IDENTITY(self, data): 
        k = keys.Key.fromString(data, type='private_blob') # not wrapped in NS here
        self.factory.keys[k.blob()] = (k, k.comment)
        self.sendResponse(AGENT_SUCCESS, '')

    def agentc_REMOVE_IDENTITY(self, data): 
        blob, _ = getNS(data)
        k = keys.Key.fromString(blob, type='blob')
        del self.factory.keys[k.blob()]
        self.sendResponse(AGENT_SUCCESS, '')

    def agentc_REMOVE_ALL_IDENTITIES(self, data): 
        assert data == ''
        self.factory.keys = {}
        self.sendResponse(AGENT_SUCCESS, '')

    # v1 messages that we ignore because we don't keep v1 keys
    # open-ssh sends both v1 and v2 commands, so we have to
    # do no-ops for v1 commands or we'll get "bad request" errors

    def agentc_REQUEST_RSA_IDENTITIES(self, data):
        self.sendResponse(AGENT_RSA_IDENTITIES_ANSWER, struct.pack('!L', 0))

    def agentc_REMOVE_RSA_IDENTITY(self, data):
        self.sendResponse(AGENT_SUCCESS, '')

    def agentc_REMOVE_ALL_RSA_IDENTITIES(self, data):
        self.sendResponse(AGENT_SUCCESS, '')

AGENTC_REQUEST_RSA_IDENTITIES   = 1
AGENT_RSA_IDENTITIES_ANSWER     = 2
AGENT_FAILURE                   = 5
AGENT_SUCCESS                   = 6

AGENTC_REMOVE_RSA_IDENTITY         = 8
AGENTC_REMOVE_ALL_RSA_IDENTITIES   = 9

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
