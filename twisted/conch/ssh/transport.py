# -*- test-case-name: twisted.test.test_conch -*-
#
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

"""The lowest level SSH protocol.  This handles the key negotiation, the encryption and the compression.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

from __future__ import nested_scopes

# base library imports
import struct
import md5
import sha
import zlib
import math # for math.log

# external library imports
from Crypto import Util
from Crypto.Cipher import XOR
from Crypto.PublicKey import RSA
from Crypto.Util import randpool

# twisted imports
from twisted.conch import error
from twisted.internet import protocol, defer
from twisted.python import log

# sibling importsa
from common import NS, getNS, MP, getMP, _MPpow, ffs, entropy # ease of use
import keys


class SSHTransportBase(protocol.Protocol):
    protocolVersion = '2.0'
    version = 'Twisted'
    comment = ''
    ourVersionString = ('SSH-'+protocolVersion+'-'+version+' '+comment).strip()

    supportedCiphers = ['aes256-ctr', 'aes256-cbc', 'aes192-ctr', 'aes192-cbc', 
                        'aes128-ctr', 'aes128-cbc', 'cast128-ctr', 
                        'cast128-cbc', 'blowfish-ctr', 'blowfish', 'idea-ctr'
                        'idea-cbc', '3des-ctr', '3des-cbc']
    supportedMACs = ['hmac-sha1', 'hmac-md5']
    supportedKeyExchanges = ['diffie-hellman-group-exchange-sha1', 
                             'diffie-hellman-group1-sha1']
    supportedPublicKeys = ['ssh-rsa', 'ssh-dss']
    supportedCompressions = ['none', 'zlib']
    supportedLanguages = ()

    gotVersion = 0
    ignoreNextPacket = 0
    buf = ''
    outgoingPacketSequence = 0
    incomingPacketSequence = 0
    currentEncryptions = None
    outgoingCompression = None
    incomingCompression = None
    sessionID = None
    isAuthorized = 0
    service = None

    def connectionLost(self, reason):
        if self.service:
            self.service.serviceStopped()
        if hasattr(self, 'avatar'):
            self.logoutFunction()
        log.msg('connection lost')

    def connectionMade(self):
        self.transport.write('%s\r\n'%(self.ourVersionString))
        self.sendKexInit()

    def sendKexInit(self):
        self.ourKexInitPayload = chr(MSG_KEXINIT)+entropy.get_bytes(16)+ \
                       NS(','.join(self.supportedKeyExchanges))+ \
                       NS(','.join(self.supportedPublicKeys))+ \
                       NS(','.join(self.supportedCiphers))+ \
                       NS(','.join(self.supportedCiphers))+ \
                       NS(','.join(self.supportedMACs))+ \
                       NS(','.join(self.supportedMACs))+ \
                       NS(','.join(self.supportedCompressions))+ \
                       NS(','.join(self.supportedCompressions))+ \
                       NS(','.join(self.supportedLanguages))+ \
                       NS(','.join(self.supportedLanguages))+ \
                       '\000'+'\000\000\000\000'
        self.sendPacket(MSG_KEXINIT, self.ourKexInitPayload[1:])

    def sendPacket(self, messageType, payload):
        payload = chr(messageType)+payload
        if self.outgoingCompression:
            payload = self.outgoingCompression.compress(payload)
            payload = payload+self.outgoingCompression.flush(2)
        if self.currentEncryptions:
            bs = self.currentEncryptions.enc_block_size
        else:
            bs = 8
        totalSize = 5+len(payload)
        lenPad = bs-(totalSize%bs)
        if lenPad < 4:
            lenPad = lenPad+bs
        randomPad = entropy.get_bytes(lenPad)
        packet = struct.pack('!LB', 1+len(payload)+lenPad, lenPad)+ \
                payload+randomPad
        assert len(packet)%bs == 0, '%s extra bytes in packet'%(len(packet)%bs)
        if self.currentEncryptions:
            encPacket = self.currentEncryptions.encrypt(packet)
            assert len(encPacket) == len(packet), '%s %s'%(len(encPacket), len(packet))
        else:
            encPacket = packet
        if self.currentEncryptions:
            d = self.currentEncryptions.makeMAC(self.outgoingPacketSequence, packet)
            encPacket = encPacket+d
        self.transport.write(encPacket)
        self.outgoingPacketSequence+=1

    def getPacket(self):
        bs = self.currentEncryptions and self.currentEncryptions.dec_block_size or 8
        ms = self.currentEncryptions and self.currentEncryptions.verify_digest_size or 0
        if len(self.buf) < bs: return # not enough data
        if not hasattr(self, 'first'):
            if self.currentEncryptions:
                first = self.currentEncryptions.decrypt(self.buf[: bs])
            else:
                first = self.buf[: bs]
        else:
            first = self.first
            del self.first
        packetLen, randomLen = struct.unpack('!LB', first[: 5])
        if packetLen > 1048576: # 1024 ** 2
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, 'bad packet length %s'%packetLen)
            return
        if len(self.buf) < packetLen+4+ms:
            self.first = first
            return # not enough packet
        if(packetLen+4)%bs != 0:
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, 'bad packet mod (%s%%%s == %s'%(packetLen+4, bs, (packetLen+4)%bs))
            return
        encData, self.buf = self.buf[: 4+packetLen], self.buf[4+packetLen:]
        if self.currentEncryptions:
            packet = first+self.currentEncryptions.decrypt(encData[bs:])
        else:
            packet = encData
        if len(packet) != 4+packetLen:
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, 'bad packet length')
            return
        if ms: 
            macData, self.buf = self.buf[:ms],  self.buf[ms:]
            if not self.currentEncryptions.verify(self.incomingPacketSequence, packet, macData):
                self.sendDisconnect(DISCONNECT_MAC_ERROR, 'bad MAC')
                return
        payload = packet[5: 4+packetLen-randomLen]
        if self.incomingCompression:
            try:
                payload = self.incomingCompression.decompress(payload)
            except zlib.error:
                self.sendDisconnect(DISCONNECT_COMPRESSION_ERROR, 'compression error')
                return
        self.incomingPacketSequence+=1
        return payload

    def dataReceived(self, data):
        self.buf = self.buf+data
        if not self.gotVersion:
            parts = self.buf.split('\n')
            for p in parts:
                if p[: 4] == 'SSH-':
                    self.gotVersion = 1
                    self.otherVersionString = p.strip()
                    if p.split('-')[1]not in('1.99', '2.0'): # bad version
                        self.sendDisconnect(DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED, 'bad version %s'%p.split('-')[1])
                        return
                    i = parts.index(p)
                    self.buf = '\n'.join(parts[i+1:])
        packet = self.getPacket()
        while packet:
            messageNum = ord(packet[0])
            if messageNum < 50:
                messageType = messages[messageNum][4:]
                f = getattr(self, 'ssh_%s'%messageType, None)
                if f:
                    f(packet[1:])
                else:
                    log.msg("couldn't handle %s"%messageType)
                    log.msg(repr(packet[1:]))
                    self.sendUnimplemented()
            elif self.service:
                self.service.packetReceived(ord(packet[0]), packet[1:])
            else:
                log.msg("couldn't handle %s"%messageNum)
                log.msg(repr(packet[1:]))
                self.sendUnimplemented()
            packet = self.getPacket()

    def ssh_DISCONNECT(self, packet):
        reasonCode = struct.unpack('>L', packet[: 4])[0]
        description, foo = getNS(packet[4:])
        self.receiveError(reasonCode, description)
        self.transport.loseConnection()

    def ssh_IGNORE(self, packet): pass

    def ssh_UNIMPLEMENTED(self, packet):
        seqnum = struct.unpack('>L', packet)
        self.receiveUnimplemented(seqnum)

    def ssh_DEBUG(self, packet):
        alwaysDisplay = ord(packet[0])
        message, lang, foo = getNS(packet, 2)
        self.receiveDebug(alwaysDisplay, message, lang)

    def setService(self, service):
        log.msg('starting service %s'%service.name)
        if self.service:
            self.service.serviceStopped()
        self.service = service
        service.transport = self
        self.service.serviceStarted()

    def sendDebug(self, message, alwaysDisplay = 0, language = ''):
        self.sendPacket(MSG_DEBUG, chr(alwaysDisplay)+NS(message)+NS(language))

    def sendIgnore(self, message):
        self.sendPacket(MSG_IGNORE, NS(message))

    def sendUnimplemented(self):
        seqnum = self.incomingPacketSequence
        self.sendPacket(MSG_UNIMPLEMENTED, struct.pack('!L', seqnum))

    def sendDisconnect(self, reason, desc):
        self.sendPacket(MSG_DISCONNECT, struct.pack('>L', reason)+NS(desc)+NS(''))
        log.msg('Disconnecting with error, code %s\nreason: %s'%(reason, desc))
        self.transport.loseConnection()

    # client methods
    def receiveError(self, reasonCode, description):
        log.msg('Got remote error, code %s\nreason: %s'%(reasonCode, description))

    def receiveUnimplemented(self, seqnum):
        log.msg('other side unimplemented packet #%s'%seqnum)

    def receiveDebug(self, alwaysDisplay, message, lang):
        if alwaysDisplay:
            log.msg('Remote Debug Message:', message)

    def isEncrypted(self, direction = "out"):
        """direction must be in ["out", "in", "both"]
        """
        if self.currentEncryptions == None:
            return 0
        elif direction == "out":
            return self.currentEncryptions.outCip != None
        elif direction == "in":
            return self.currentEncryptions.outCip != None
        elif direction == "both":
            return self.isEncrypted("in")and self.isEncrypted("out")
        else:
            raise TypeError, 'direction must be "out", "in", or "both"'

    def isVerified(self, direction = "out"):
        """direction must be in ["out", "in", "both"]
        """
        if self.currentEncryptions == None:
            return 0
        elif direction == "out":
            return self.currentEncryptions.outMAC != None
        elif direction == "in":
            return self.currentEncryptions.outCMAC != None
        elif direction == "both":
            return self.isVerified("in")and self.isVerified("out")
        else:
            raise TypeError, 'direction must be "out", "in", or "both"'

class SSHServerTransport(SSHTransportBase):
    isClient = 0
    def ssh_KEXINIT(self, packet):
        self.clientKexInitPayload = chr(MSG_KEXINIT)+packet
        #cookie = packet[: 16] # taking this is useless
        k = getNS(packet[16:], 10)
        strings, rest = k[:-1], k[-1]
        kexAlgs, keyAlgs, encCS, encSC, macCS, macSC, compCS, compSC, langCS, langSC =  \
           [s.split(',')for s in strings]
        if ord(rest[0]): # first_kex_packet_follows
            if kexAlgs[0] != self.supportedKeyExchanges[0]or \
               keyAlgs[0] != self.supportedPublicKeys[0]or \
               not ffs(encSC, self.supportedCiphers)or \
               not ffs(encCS, self.supportedCiphers)or \
               not ffs(macSC, self.supportedMACs)or \
               not ffs(macCS, self.supportedMACs)or \
               not ffs(compCS, self.supportedCompressions)or \
               not ffs(compSC, self.supportedCompressions):
                self.ignoreNextPacket = 1 # guess was wrong
        self.kexAlg = ffs(kexAlgs, self.supportedKeyExchanges)
        self.keyAlg = ffs(keyAlgs, self.supportedPublicKeys)
        self.nextEncryptions = SSHCiphers(
        ffs(encSC, self.supportedCiphers), 
            ffs(encCS, self.supportedCiphers), 
            ffs(macSC, self.supportedMACs), 
            ffs(macCS, self.supportedMACs), 
         )
        self.outgoingCompressionType = ffs(compSC, self.supportedCompressions)
        self.incomingCompressionType = ffs(compCS, self.supportedCompressions)
        if None in(self.kexAlg, self.keyAlg, self.outgoingCompressionType, self.incomingCompressionType):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return
        if None in self.nextEncryptions.__dict__.values():
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return
        log.msg('kex alg, key alg: %s %s'%(self.kexAlg, self.keyAlg))
        log.msg('server->client: %s %s %s'%(self.nextEncryptions.outCipType, 
                                            self.nextEncryptions.outMacType, 
                                            self.outgoingCompressionType))
        log.msg('client->server: %s %s %s'%(self.nextEncryptions.inCipType, 
                                            self.nextEncryptions.inMacType, 
                                            self.incomingCompressionType))


    def ssh_KEX_DH_GEX_REQUEST_OLD(self, packet):
        if self.ignoreNextPacket:
            self.ignoreNextPacket = 0
            return
        if self.kexAlg == 'diffie-hellman-group1-sha1': # this is really KEXDH_INIT
            clientDHPubKey, foo = getMP(packet)
            y = Util.number.getRandomNumber(16, entropy.get_bytes)
            f = pow(DH_GENERATOR, y, DH_PRIME)
            sharedSecret = _MPpow(clientDHPubKey, y, DH_PRIME)
            h = sha.new()
            h.update(NS(self.otherVersionString))
            h.update(NS(self.ourVersionString))
            h.update(NS(self.clientKexInitPayload))
            h.update(NS(self.ourKexInitPayload))
            h.update(NS(self.factory.publicKeys[self.keyAlg]))
            h.update(MP(clientDHPubKey))
            h.update(MP(f))
            h.update(sharedSecret)
            exchangeHash = h.digest()
            self.sendPacket(MSG_KEXDH_REPLY, NS(self.factory.publicKeys[self.keyAlg])+ \
                           MP(f)+NS(keys.signData(self.factory.privateKeys[self.keyAlg], exchangeHash)))
            self._keySetup(sharedSecret, exchangeHash)
        elif self.kexAlg == 'diffie-hellman-group-exchange-sha1':
            self.kexAlg = 'diffie-hellman-group-exchange-sha1-old'
            self.ideal = struct.unpack('>L', packet)[0]
            self.g, self.p = self.factory.getDHPrime(self.ideal)
            self.sendPacket(MSG_KEX_DH_GEX_GROUP, MP(self.p)+MP(self.g))
        else:
            raise error.ConchError('bad kexalg: %s'%self.kexAlg)

    def ssh_KEX_DH_GEX_REQUEST(self, packet):
        if self.ignoreNextPacket:
            self.ignoreNextPacket = 0
            return
        self.min, self.ideal, self.max = struct.unpack('>3L', packet)
        self.g, self.p = self.factory.getDHPrime(self.ideal)
        self.sendPacket(MSG_KEX_DH_GEX_GROUP, MP(self.p)+MP(self.g))

    def ssh_KEX_DH_GEX_INIT(self, packet):
        clientDHPubKey, foo = getMP(packet)

        # if y < 1024, openssh will reject us: "bad server public DH value".
        # y<1024 means f will be short, and of the form 2^y, so an observer
        # could trivially derive our secret y from f. Openssh detects this
        # and complains, so avoid creating such values by requiring y to be
        # larger than ln2(self.p)

        # TODO: we should also look at the value they send to us and reject
        # insecure values of f (if g==2 and f has a single '1' bit while the
        # rest are '0's, then they must have used a small y also).

        # TODO: This could be computed when self.p is set up
        #  or do as openssh does and scan f for a single '1' bit instead

        minimum = long(math.floor(math.log(self.p) / math.log(2)) + 1)
        tries = 0
        pSize = Util.number.size(self.p)
        y = Util.number.getRandomNumber(pSize, entropy.get_bytes)
        while tries < 10 and y < minimum:
            tries += 1
            y = Util.number.getRandomNumber(pSize, entropy.get_bytes)
        assert(y >= minimum) # TODO: test_conch just hangs if this is hit
        # the chance of it being hit are really really low

        f = pow(self.g, y, self.p)
        sharedSecret = _MPpow(clientDHPubKey, y, self.p)
        h = sha.new()
        h.update(NS(self.otherVersionString))
        h.update(NS(self.ourVersionString))
        h.update(NS(self.clientKexInitPayload))
        h.update(NS(self.ourKexInitPayload))
        h.update(NS(self.factory.publicKeys[self.keyAlg]))
        if self.kexAlg == 'diffie-hellman-group-exchange-sha1':
            h.update(struct.pack('>3L', self.min, self.ideal, self.max))
        else:
            h.update(struct.pack('>L', self.ideal))
        h.update(MP(self.p))
        h.update(MP(self.g))
        h.update(MP(clientDHPubKey))
        h.update(MP(f))
        h.update(sharedSecret)
        exchangeHash = h.digest()
        self.sendPacket(MSG_KEX_DH_GEX_REPLY, NS(self.factory.publicKeys[self.keyAlg])+ \
                       MP(f)+NS(keys.signData(self.factory.privateKeys[self.keyAlg], exchangeHash)))
        self._keySetup(sharedSecret, exchangeHash)

    def ssh_NEWKEYS(self, packet):
        if packet != '':
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, "NEWKEYS takes no data")
        self.currentEncryptions = self.nextEncryptions
        if self.outgoingCompressionType == 'zlib':
            self.outgoingCompression = zlib.compressobj(6)
            #self.outgoingCompression.compress = lambda x: self.outgoingCompression.compress(x) + self.outgoingCompression.flush(zlib.Z_SYNC_FLUSH)
        if self.incomingCompressionType == 'zlib':
            self.incomingCompression = zlib.decompressobj()

    def ssh_SERVICE_REQUEST(self, packet):
        service, rest = getNS(packet)
        cls = self.factory.getService(self, service)
        if not cls:
            self.sendDisconnect(DISCONNECT_SERVICE_NOT_AVAILABLE, "don't have service %s"%service)
            return
        else:
            self.sendPacket(MSG_SERVICE_ACCEPT, NS(service))
            self.setService(cls())

    def _keySetup(self, sharedSecret, exchangeHash):
        if not self.sessionID:
            self.sessionID = exchangeHash
        initIVCS = self._getKey('A', sharedSecret, exchangeHash)
        initIVSC = self._getKey('B', sharedSecret, exchangeHash)
        encKeyCS = self._getKey('C', sharedSecret, exchangeHash)
        encKeySC = self._getKey('D', sharedSecret, exchangeHash)
        integKeyCS = self._getKey('E', sharedSecret, exchangeHash)
        integKeySC = self._getKey('F', sharedSecret, exchangeHash)
        self.nextEncryptions.setKeys(initIVSC, encKeySC, initIVCS, encKeyCS, integKeySC, integKeyCS)
        self.sendPacket(MSG_NEWKEYS, '')

    def _getKey(self, c, sharedSecret, exchangeHash):
        k1 = sha.new(sharedSecret+exchangeHash+c+self.sessionID).digest()
        k2 = sha.new(sharedSecret+exchangeHash+k1).digest()
        return k1+k2

class SSHClientTransport(SSHTransportBase):
    isClient = 1

    def connectionMade(self):
        SSHTransportBase.connectionMade(self)
        self._gotNewKeys = 0

    def ssh_KEXINIT(self, packet):
        self.serverKexInitPayload = chr(MSG_KEXINIT)+packet
        #cookie = packet[: 16] # taking this is unimportant
        k = getNS(packet[16:], 10)
        strings, rest = k[:-1], k[-1]
        kexAlgs, keyAlgs, encCS, encSC, macCS, macSC, compCS, compSC, langCS, langSC =  \
           [s.split(',')for s in strings]
        self.kexAlg = ffs(self.supportedKeyExchanges, kexAlgs)
        self.keyAlg = ffs(self.supportedPublicKeys, keyAlgs)
        self.nextEncryptions = SSHCiphers(
        ffs(self.supportedCiphers, encCS), 
            ffs(self.supportedCiphers, encSC), 
            ffs(self.supportedMACs, macCS), 
            ffs(self.supportedMACs, macSC), 
         )
        self.outgoingCompressionType = ffs(self.supportedCompressions, compCS)
        self.incomingCompressionType = ffs(self.supportedCompressions, compSC)
        if None in(self.kexAlg, self.keyAlg, self.outgoingCompressionType, self.incomingCompressionType):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return
        if None in self.nextEncryptions.__dict__.values():
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return
        log.msg('kex alg, key alg: %s %s'%(self.kexAlg, self.keyAlg))
        log.msg('client->server: %s %s %s'%(self.nextEncryptions.outCipType, 
                                            self.nextEncryptions.outMacType, 
                                            self.outgoingCompressionType))
        log.msg('server->client: %s %s %s'%(self.nextEncryptions.inCipType, 
                                            self.nextEncryptions.inMacType, 
                                            self.incomingCompressionType))

        if self.kexAlg == 'diffie-hellman-group1-sha1':
            self.x = Util.number.getRandomNumber(512, entropy.get_bytes)
            self.DHpubKey = pow(DH_GENERATOR, self.x, DH_PRIME)
            self.sendPacket(MSG_KEXDH_INIT, MP(self.DHpubKey))
        else:
            self.sendPacket(MSG_KEX_DH_GEX_REQUEST_OLD, '\x00\x00\x08\x00')

    def ssh_KEX_DH_GEX_GROUP(self, packet):
        if self.kexAlg == 'diffie-hellman-group1-sha1':
            pubKey, packet = getNS(packet)
            f, packet = getMP(packet)
            signature, packet = getNS(packet)
            fingerprint = ':'.join(map(lambda c: '%02x'%ord(c), md5.new(pubKey).digest()))
            d = self.verifyHostKey(pubKey, fingerprint)
            d.addCallback(self._continueGEX_GROUP, pubKey, f, signature)
            d.addErrback(lambda unused,self=self:self.sendDisconnect(DISCONNECT_HOST_KEY_NOT_VERIFIABLE, 'bad host key'))
        else:
            self.p, rest = getMP(packet)
            self.g, rest = getMP(rest)
            self.x = getMP('\x00\x00\x00\x40'+entropy.get_bytes(64))[0]
            self.DHpubKey = pow(self.g, self.x, self.p)
            self.sendPacket(MSG_KEX_DH_GEX_INIT, MP(self.DHpubKey))

    def _continueGEX_GROUP(self, ignored, pubKey, f, signature):
        serverKey = keys.getPublicKeyObject(pubKey)
        sharedSecret = _MPpow(f, self.x, DH_PRIME)
        h = sha.new()
        h.update(NS(self.ourVersionString))
        h.update(NS(self.otherVersionString))
        h.update(NS(self.ourKexInitPayload))
        h.update(NS(self.serverKexInitPayload))
        h.update(NS(pubKey))
        h.update(MP(self.DHpubKey))
        h.update(MP(f))
        h.update(sharedSecret)
        exchangeHash = h.digest()
        if not keys.verifySignature(serverKey, signature, exchangeHash):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, 'bad signature')
            return
        self._keySetup(sharedSecret, exchangeHash)

    def ssh_KEX_DH_GEX_REPLY(self, packet):
        pubKey, packet = getNS(packet)
        f, packet = getMP(packet)
        signature, packet = getNS(packet)
        fingerprint = ':'.join(map(lambda c: '%02x'%ord(c), md5.new(pubKey).digest()))
        d = self.verifyHostKey(pubKey, fingerprint)
        d.addCallback(self._continueGEX_REPLY, pubKey, f, signature)
        d.addErrback(lambda unused, self=self: self.sendDisconnect(DISCONNECT_HOST_KEY_NOT_VERIFIABLE, 'bad host key'))

    def _continueGEX_REPLY(self, ignored, pubKey, f, signature):
        serverKey = keys.getPublicKeyObject(pubKey)
        sharedSecret = _MPpow(f, self.x, self.p)
        h = sha.new()
        h.update(NS(self.ourVersionString))
        h.update(NS(self.otherVersionString))
        h.update(NS(self.ourKexInitPayload))
        h.update(NS(self.serverKexInitPayload))
        h.update(NS(pubKey))
        h.update('\x00\x00\x08\x00')
        h.update(MP(self.p))
        h.update(MP(self.g))
        h.update(MP(self.DHpubKey))
        h.update(MP(f))
        h.update(sharedSecret)
        exchangeHash = h.digest()
        if not keys.verifySignature(serverKey, signature, exchangeHash):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, 'bad signature')
            return
        self._keySetup(sharedSecret, exchangeHash)

    def _keySetup(self, sharedSecret, exchangeHash):
        if not self.sessionID:
            self.sessionID = exchangeHash
        initIVCS = self._getKey('A', sharedSecret, exchangeHash)
        initIVSC = self._getKey('B', sharedSecret, exchangeHash)
        encKeyCS = self._getKey('C', sharedSecret, exchangeHash)
        encKeySC = self._getKey('D', sharedSecret, exchangeHash)
        integKeyCS = self._getKey('E', sharedSecret, exchangeHash)
        integKeySC = self._getKey('F', sharedSecret, exchangeHash)
        self.nextEncryptions.setKeys(initIVCS, encKeyCS, initIVSC, encKeySC, integKeyCS, integKeySC)
        self.sendPacket(MSG_NEWKEYS, '')
        if self._gotNewKeys:
            self.ssh_NEWKEYS('')

    def _getKey(self, c, sharedSecret, exchangeHash):
        k1 = sha.new(sharedSecret+exchangeHash+c+self.sessionID).digest()
        k2 = sha.new(sharedSecret+exchangeHash+k1).digest()
        return k1+k2

    def ssh_NEWKEYS(self, packet):
        if packet != '':
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, "NEWKEYS takes no data")
        if not hasattr(self.nextEncryptions, 'outCip'):
            self._gotNewKeys = 1
            return
        self.currentEncryptions = self.nextEncryptions
        if self.outgoingCompressionType == 'zlib':
            self.outgoingCompression = zlib.compressobj(6)
            #self.outgoingCompression.compress = lambda x: self.outgoingCompression.compress(x) + self.outgoingCompression.flush(zlib.Z_SYNC_FLUSH)
        if self.incomingCompressionType == 'zlib':
            self.incomingCompression = zlib.decompressobj()
        self.connectionSecure()

    def ssh_SERVICE_ACCEPT(self, packet):
        name = getNS(packet)[0]
        if name != self.instance.name:
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, "received accept for service we did not request")
        self.setService(self.instance)

    def requestService(self, instance):
        """
        Request that a service be run over this transport.

        @type instance: subclass of C{twisted.conch.ssh.service.SSHService}
        """
        self.sendPacket(MSG_SERVICE_REQUEST, NS(instance.name))
        self.instance = instance

    # client methods
    def verifyHostKey(self, hostKey, fingerprint):
        """Returns a Deferred that gets a callback if it is a valid key, or
        an errback if not.

        @type hostKey:      C{str}
        @type fingerprint:  C{str}
        @rtype:             C{Deferred}
        """
        # return  if it's good
        return defer.fail(NotImplementedError)

    def connectionSecure(self):
        """
        Called when the encryption has been set up.  Generally, 
        requestService() is called to run another service over the transport.
        """
        raise NotImplementedError

class SSHCiphers:
    cipherMap = {
        '3des-cbc':('DES3', 24, 0), 
        'blowfish-cbc':('Blowfish', 16,0 ), 
        'aes256-cbc':('AES', 32, 0), 
        'aes192-cbc':('AES', 24, 0), 
        'aes128-cbc':('AES', 16, 0), 
        'arcfour':('ARC4', 16, 0), 
        'idea-cbc':('IDEA', 16, 0), 
        'cast128-cbc':('CAST', 16, 0), 
        'aes128-ctr':('AES', 16, 1),
        'aes192-ctr':('AES', 24, 1),
        'aes256-ctr':('AES', 32, 1),
        '3des-ctr':('DES3', 24, 1),
        'blowfish-ctr':('Blowfish', 16, 1),
        'idea-ctr':('IDEA', 16, 1),
        'cast128-ctr':('CAST', 16, 1),
        'none':(None, None), 
     }
    macMap = {
        'hmac-sha1': 'sha', 
        'hmac-md5': 'md5', 
        'none': None, 
     }

    def __init__(self, outCip, inCip, outMac, inMac):
        self.outCipType = outCip
        self.inCipType = inCip
        self.outMacType = outMac
        self.inMacType = inMac

    def setKeys(self, outIV, outKey, inIV, inKey, outInteg, inInteg):
        self.outCip = self._getCipher(self.outCipType, outIV, outKey)
        self.enc_block_size = self.outCip.block_size
        self.inCip = self._getCipher(self.inCipType, inIV, inKey)
        self.dec_block_size = self.inCip.block_size
        self.outMAC = self._getMAC(self.outMacType, outInteg)
        self.inMAC = self._getMAC(self.inMacType, inInteg)
        self.verify_digest_size = self.inMAC[2]

    def _getCipher(self, cip, iv, key):
        modName, keySize, counterMode = self.cipherMap[cip]
        if not modName: return # no cipher
        mod = __import__('Crypto.Cipher.%s'%modName, {}, {}, 'x')
        if counterMode:
            return mod.new(key[:keySize], mod.MODE_CTR, iv[:mod.block_size], counter=_Counter(iv, mod))
        else:
            return mod.new(key[: keySize], mod.MODE_CBC, iv[: mod.block_size])

    def _getMAC(self, mac, key):
        modName = self.macMap[mac]
        if not modName: return
        mod = __import__(modName, {}, {}, '')
        if not hasattr(mod, 'digest_size'):
            ds = len(mod.new().digest())
        else:
            ds = mod.digest_size
        key = key[: ds]+'\x00'*(64-ds)
        return mod, key, ds

    def encrypt(self, blocks):
        return self.outCip and self.outCip.encrypt(blocks) or blocks

    def decrypt(self, blocks):
        return self.inCip and self.inCip.decrypt(blocks) or blocks

    def makeMAC(self, seqid, data):
        data = struct.pack('>L', seqid)+data
        mod, key, ds = self.outMAC
        inner = mod.new(XOR.new('\x36').encrypt(key)+data)
        outer = mod.new(XOR.new('\x5c').encrypt(key)+inner.digest())
        return outer.digest()

    def verify(self, seqid, data, mac):
        data = struct.pack('>L', seqid)+data
        mod, key, ds = self.inMAC
        inner = mod.new(XOR.new('\x36').encrypt(key)+data)
        outer = mod.new(XOR.new('\x5c').encrypt(key)+inner.digest())
        return mac == outer.digest()

class _Counter:
    def __init__(self, iv, mod):
        iv=iv[:mod.block_size]
        self.count = getMP('\xff\xff\xff\xff'+iv)[0]
        self.bs = mod.block_size
    def __call__(self):
        ret = MP(self.count)[4:]
        if ret[0]=='\x00':
            ret=ret[1:]
        if len(ret) < self.bs:
            ret = '\x00'*(self.bs-len(ret)) + ret
        self.count += 1
        if self.count == 2L ** self.bs:
            self.count = 0
        return ret


def buffer_dump(b, title = None):
    r = title or ''
    while b:
        c, b = b[: 16], b[16:]
        while c:
            a, c = c[: 2], c[2:]
            if len(a) == 2:
                r = r+'%02x%02x '%(ord(a[0]), ord(a[1]))
            else:
                r = r+'%02x'%ord(a[0])
        r = r+'\n'
    return r

DH_PRIME = 179769313486231590770839156793787453197860296048756011706444423684197180216158519368947833795864925541502180565485980503646440548199239100050792877003355816639229553136239076508735759914822574862575007425302077447712589550957937778424442426617334727629299387668709205606050270810842907692932019128194467627007L
DH_GENERATOR = 2L

MSG_DISCONNECT = 1
MSG_IGNORE = 2
MSG_UNIMPLEMENTED = 3
MSG_DEBUG = 4
MSG_SERVICE_REQUEST = 5
MSG_SERVICE_ACCEPT = 6
MSG_KEXINIT = 20
MSG_NEWKEYS = 21
MSG_KEXDH_INIT = 30
MSG_KEXDH_REPLY = 31
MSG_KEX_DH_GEX_REQUEST_OLD = 30
MSG_KEX_DH_GEX_REQUEST = 34
MSG_KEX_DH_GEX_GROUP = 31
MSG_KEX_DH_GEX_INIT = 32
MSG_KEX_DH_GEX_REPLY = 33

DISCONNECT_HOST_NOT_ALLOWED_TO_CONNECT = 1
DISCONNECT_PROTOCOL_ERROR = 2
DISCONNECT_KEY_EXCHANGE_FAILED = 3
DISCONNECT_RESERVED = 4
DISCONNECT_MAC_ERROR = 5
DISCONNECT_COMPRESSION_ERROR = 6
DISCONNECT_SERVICE_NOT_AVAILABLE = 7
DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED = 8
DISCONNECT_HOST_KEY_NOT_VERIFIABLE = 9
DISCONNECT_CONNECTION_LOST = 10
DISCONNECT_BY_APPLICATION = 11
DISCONNECT_TOO_MANY_CONNECTIONS = 12
DISCONNECT_AUTH_CANCELLED_BY_USER = 13
DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE = 14
DISCONNECT_ILLEGAL_USER_NAME = 15

messages = {}
import transport
for v in dir(transport):
    if v[: 4] == 'MSG_':
        messages[getattr(transport, v)] = v # doesn't handle doubles

