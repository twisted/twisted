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
# base library imports
import struct
import md5
import sha
import zlib

# external library imports
from Crypto import Util
from Crypto.Hash import HMAC
from Crypto.PublicKey import RSA

# twisted imports
from twisted.internet import protocol

# sibling importsa
#import keys
from common import NS, getNS, MP, getMP, ffs
import keys
#RSAkey = cPickle.load(open('/c/rsakey'))

class SSHTransportBase(protocol.Protocol):
    protocolVersion = '2.0'
    serverVersion = 'Twisted'
    comment = ''
    ourVersionString = ('SSH-'+protocolVersion+'-'+serverVersion+' '+comment).strip()

    supportedCiphers = ('aes256-cbc', 'aes192-cbc', 'aes128-cbc', 'cast128-cbc',
                        'blowfish', 'idea-cbc', '3des-cbc', 'arcfour', 'none')
    supportedMACs = ('hmac-sha1', 'hmac-md5', 'none')
    supportedKeyExchanges = (#'diffie-hellman-group1-sha1',
        'diffie-hellman-group-exchange-sha1',)
#                             'diffie-hellman-group1-sha1')
    supportedPublicKeys = ('ssh-rsa', 'ssh-dss', )
    supportedCompressions = ('none',) # compression doesn't work
    supportedLanguages = ()

    gotVersion = 0
    buf = ''
    outgoingPacketSequence = 0 
    incomingPacketSequence = 0
    currentEncryptions = None
    outgoingCompression = None
    incomingCompression = None
    sessionID = None
    service = None

    def connectionLost(self):
        print 'connection lost'
        #from twisted.internet import reactor
        #reactor.stop()

    def connectionMade(self):
        print 'woo we got a connection'
        self.transport.write('%s\r\n' % (self.ourVersionString)
                            )
        self.ourKexInitPayload = chr(MSG_KEXINIT) + open('/dev/random').read(16) + \
                        NS(','.join(self.supportedKeyExchanges)) + \
                        NS(','.join(self.supportedPublicKeys)) + \
                        NS(','.join(self.supportedCiphers)) + \
                        NS(','.join(self.supportedCiphers)) + \
                        NS(','.join(self.supportedMACs)) + \
                        NS(','.join(self.supportedMACs)) + \
                        NS(','.join(self.supportedCompressions)) + \
                        NS(','.join(self.supportedCompressions)) + \
                        NS(','.join(self.supportedLanguages)) + \
                        NS(','.join(self.supportedLanguages)) + \
                        '\000' + '\000\000\000\000'
        self.sendPacket(MSG_KEXINIT, self.ourKexInitPayload[1:])
        #self.sendDebug('this is a test', 1)

    def sendPacket(self, messageType, payload):
        payload = chr(messageType) + payload
        if self.outgoingCompression:
            payload = self.outgoingCompression.compress(payload)
            payload = payload + self.outgoingCompression.flush(2)
        if self.currentEncryptions:
            bs = self.currentEncryptions.enc_block_size
        else:
            bs = 8
        totalSize = 5 + len(payload)
        lenPad = bs - (totalSize % bs)
        if lenPad < 4:
            lenPad = lenPad + bs
        randomPad = open('/dev/random').read(lenPad)
        packet = struct.pack('!LB', 1 + len(payload) + lenPad, lenPad) + \
                 payload + randomPad
        assert len(packet)%bs == 0, '%s extra bytes in packet' % (len(packet)%bs)
        #print 'plain:\t',buffer_dump(packet)
        if self.currentEncryptions:
            encPacket = self.currentEncryptions.encrypt(packet)
            assert len(encPacket)==len(packet), '%s %s' % (len(encPacket),len(packet))
            #print 'encrypted:\t', buffer_dump(encPacket)
        else:
            encPacket = packet
        if self.currentEncryptions:
            d = self.currentEncryptions.makeMAC(self.outgoingPacketSequence, packet)
            encPacket = encPacket + d
        self.transport.write(encPacket)
        self.outgoingPacketSequence += 1

    def getPacket(self):
        bs = self.currentEncryptions and self.currentEncryptions.dec_block_size  or 8
        if len(self.buf) < bs: return # not enough data
        if self.currentEncryptions:
            first = self.currentEncryptions.decrypt(self.buf[:bs])
        else:
            first = self.buf[:bs]
        packetLen, randomLen = struct.unpack('!LB',first[:5])
        if (packetLen+4)%bs != 0:
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, 'bad packet length')
            return
        if len(self.buf) < packetLen: return # not enough packet
        encData, self.buf = self.buf[:4+packetLen], self.buf[4+packetLen:]
        if self.currentEncryptions:
            packet = first + self.currentEncryptions.decrypt(encData[bs:])
        else:
            packet = encData
        if len(packet)!=4+packetLen:
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR, 'bad packet length')
            return
        #print buffer_dump(packet)
        if self.currentEncryptions:
            macData, self.buf = self.buf[:self.currentEncryptions.verify_digest_size], \
                                self.buf[self.currentEncryptions.verify_digest_size:]
            if not self.currentEncryptions.verify(self.incomingPacketSequence, packet, macData):
                self.sendDisconnect(DISCONNECT_MAC_ERROR, 'bad MAC')
                return
        payload = packet[5:4+packetLen-randomLen]
        if self.incomingCompression:
            try:
                payload = self.incomingCompression.decompress(payload)
            except zlib.error, e:
                self.sendDisconnect(DISCONNECT_COMPRESSION_ERROR, e)
                return
        self.incomingPacketSequence += 1
        return payload

    def dataReceived(self, data):
        self.buf = self.buf + data
        if not self.gotVersion:
            parts = self.buf.split('\n')
            for p in parts:
                if p[:4]=='SSH-':
                    self.gotVersion = 1
                    print 'got ssh version from client:', p.strip()
                    self.otherVersionString = p.strip()
                    if p.split('-')[1] not in ('1.99','2.0'): # bad version
                        self.sendDisconnect(DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED, 'bad version %s'%p.split('-')[1])
                        return
                    i = parts.index(p)
                    self.buf = '\n'.join(parts[i+1:])
        packet = self.getPacket()
        while packet:  
            messageNum = ord(packet[0])
            if messageNum < 50:
                messageType = messages[messageNum][4:]
                f = getattr(self,'ssh_%s' % messageType, None)
                if f:
                    f(packet[1:])
                else:
                    print "couldn't handle", messageType
                    print repr(packet[1:])
                    self.sendUnimplemented()
            elif self.service:
                self.service.packetReceived(ord(packet[0]), packet[1:])
            else:                     
                print "couldn't handle", messageNum
                print repr(packet[1:])
                self.sendUnimplemented()
            packet = self.getPacket()

    def ssh_DISCONNECT(self, packet):
        reasonCode = struct.unpack('>L', packet[:4])[0]
        description, foo = getNS(packet[4:])
        self.receiveError(reasonCode, description)
        self.transport.loseConnection()

    def ssh_IGNORE(self, packet): pass

    def ssh_UNIMPLEMENTED(self, packet):
        seqnum = struct.unpack('>L', packet)
        self.receiveUnimplemented(seqnum)

    def ssh_DEBUG(self, packet):
        alwaysDisplay = ord(packet[0])
        message, lang,  foo = getNS(packet, 2)
        self.receiveDebug(alwaysDisplay, message, lang)

    def setService(self, service):
        print 'setting service for',self,'to',service.name
        self.service = service
        service.transport = self
        self.service.serviceStarted()

    def sendDebug(self, message, alwaysDisplay = 0, language = ''):
        self.sendPacket(MSG_DEBUG, chr(alwaysDisplay) + NS(message) + NS(language))

    def sendUnimplemented(self):
        seqnum = self.incomingPacketSequence
        self.sendPacket(MSG_UNIMPLEMENTED, struct.pack('!L', seqnum))

    def sendDisconnect(self, reason, desc):
        self.sendPacket(MSG_DISCONNECT, struct.pack('>L', reason) + NS(desc) + NS(''))
        self.transport.loseConnection()
        
    # client methods
    def receiveError(self, reasonCode, description):
        raise 'Got remote error, code %s\nreason: %s' % (reasonCode, description)

    def receiveUnimplemented(self, seqnum):
        print 'other side unimplemented packet #%s' % seqnum

    def receiveDebug(self, alwaysDisplay, message, lang):
        if alwaysDisplay:
            print 'Remote Debug Message:', message

class SSHServerTransport(SSHTransportBase):
    def ssh_KEXINIT(self, packet):
        self.clientKexInitPayload = chr(MSG_KEXINIT) + packet
        cookie = packet[:16]
        k = getNS(packet[16:], 10)
        strings, rest = k[:-1], k[-1]
        assert rest[-1]=='\x00', 'first kex packet sent'
        kexAlgs, keyAlgs, encCS, encSC, macCS, macSC, compCS, compSC, langCS, langSC = \
            [s.split(',') for s in strings]
#        print kexAlgs, keyAlgs, encCS, encSC, macCS, macSC, compCS, compSC, langCS, langSC, repr(rest)
        kexAlg = ffs(kexAlgs, self.supportedKeyExchanges)
        self.kexAlg = kexAlg
        self.keyAlg = ffs(keyAlgs, self.supportedPublicKeys)
        self.nextEncryptions = SSHCiphers(
            ffs(encSC, self.supportedCiphers),
            ffs(encCS, self.supportedCiphers),
            ffs(macSC, self.supportedMACs),
            ffs(macCS, self.supportedMACs),
        )
        self.outgoingCompressionType = ffs(compSC, self.supportedCompressions)
        self.incomingCompressionType = ffs(compCS, self.supportedCompressions)
        if None in (self.kexAlg, self.keyAlg, self.outgoingCompressionType, self.incomingCompressionType):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return
        if None in self.nextEncryptions.__dict__.values():
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return            
#        print self.nextEncryptions.__dict__

    def ssh_KEX_DH_GEX_REQUEST_OLD(self, packet):
        if self.kexAlg == 'diffie-hellman-group1-sha1': # this is really KEXDH_INIT
            clientDHPubKey, foo = getMP(packet)
            y = Util.number.getRandomNumber(16, open('/dev/random').read)
            f = pow (DH_GENERATOR, y, DH_PRIME)
            sharedSecret = MP(pow(clientDHPubKey, y, DH_PRIME))
            h = sha.new()
            h.update(NS(self.otherVersionString))
            h.update(NS(self.ourVersionString))
            h.update(NS(self.clientKexInitPayload))
            h.update(NS(self.ourKexInitPayload))
            h.update(NS(self.factory.publicKey[self.keyAlg]))
            h.update(MP(clientDHPubKey))
            h.update(MP(f))
            h.update(sharedSecret)
            exchangeHash = h.digest()
            print 'hash', h.hexdigest()
            self.sendPacket(MSG_KEXDH_REPLY, NS(self.factory.publicKeys[self.keyAlg]) + \
                            MP(f) + NS(keys.signData(self.factory.privateKeys[self.keyAlg], exchangeHash)))
            self._keySetup(sharedSecret, exchangeHash)
        elif self.kexAlg == 'diffie-hellman-group-exchange-sha1':
            self.kexAlg =  'diffie-helmman-group-exchange-sha1-old'
            self.ideal = struct.unpack('>L', packet)[0]
            self.g, self.p = self.factory.getDHPrime(self.ideal)
            self.sendPacket(MSG_KEX_DH_GEX_GROUP, MP(self.p)+MP(self.g))
        else:
            raise self.kexAlg

    def ssh_KEX_DH_GEX_REQUEST(self, packet):
        self.min, self.ideal, self.max = struct.unpack('>3L', packet)
        self.g, self.p = self.factory.getDHPrime(self.ideal)
        self.sendPacket(MSG_KEX_DH_GEX_GROUP, MP(self.p)+MP(self.g))

    def ssh_KEX_DH_GEX_INIT(self, packet):
        clientDHPubKey, foo = getMP(packet)
        y = Util.number.getRandomNumber(16, open('/dev/random').read)
        f = pow (self.g, y, self.p)
        sharedSecret = MP(pow(clientDHPubKey, y, self.p)) 
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
#        print 'hash', h.hexdigest()
        self.sendPacket(MSG_KEX_DH_GEX_REPLY, NS(self.factory.publicKeys[self.keyAlg]) + \
                        MP(f) + NS(keys.signData(self.factory.privateKeys[self.keyAlg], exchangeHash)))
        self._keySetup(sharedSecret, exchangeHash)

    def ssh_NEWKEYS(self, packet):
        self.currentEncryptions = self.nextEncryptions
        if self.outgoingCompressionType == 'zlib':
            self.outgoingCompression = zlib.compressobj(6)
            #self.outgoingCompression.compress = lambda x: self.outgoingCompression.compress(x) + self.outgoingCompression.flush(zlib.Z_SYNC_FLUSH)
        if self.incomingCompressionType == 'zlib':
            self.incomingCompression = zlib.decompressobj()

    def ssh_SERVICE_REQUEST(self, packet):
        service, rest = getNS(packet)
        cls = self.factory.services.get(service, None)
        if not cls:
            self.sendDisconnect(DISCONNECT_SERVICE_NOT_AVAILABLE, "don't have service %s" % service)
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
        print 'set ciphers'

    def _getKey(self, c, sharedSecret, exchangeHash):
        k1 = sha.new(sharedSecret+exchangeHash+c+self.sessionID).digest()
        k2 = sha.new(sharedSecret+exchangeHash+k1).digest()
        return k1+k2

class SSHClientTransport(SSHTransportBase):
    def ssh_KEXINIT(self, packet):
        self.serverKexInitPayload = chr(MSG_KEXINIT) + packet
        cookie = packet[:16]
        k = getNS(packet[16:], 10)
        strings, rest = k[:-1], k[-1]
        kexAlgs, keyAlgs, encCS, encSC, macCS, macSC, compCS, compSC, langCS, langSC = \
            [s.split(',') for s in strings]
#        print kexAlgs, keyAlgs, encCS, encSC, macCS, macSC, compCS, compSC, langCS, langSC, repr(rest)
        kexAlg = ffs(self.supportedKeyExchanges, kexAlgs)
        self.kexAlg = kexAlg
        self.keyAlg = ffs(self.supportedPublicKeys, keyAlgs)
        self.nextEncryptions = SSHCiphers(
            ffs(self.supportedCiphers, encCS),
            ffs(self.supportedCiphers, encSC),
            ffs(self.supportedMACs, macCS),
            ffs(self.supportedMACs, macSC),
        )
        self.outgoingCompressionType = ffs(self.supportedCompressions, compCS)
        self.incomingCompressionType = ffs(self.supportedCompressions, compSC)
        if None in (self.kexAlg, self.keyAlg, self.outgoingCompressionType, self.incomingCompressionType):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return
        if None in self.nextEncryptions.__dict__.values():
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, "couldn't match all kex parts")
            return            
        if kexAlg == 'diffie-hellman-group1-sha1':
            self.x = Util.number.getRandomNumber(512, open('/dev/random').read)
            self.DHpubKey = pow(DH_GENERATOR, self.x, DH_PRIME)
            self.sendPacket(MSG_KEXDH_INIT, MP(self.DHpubKey))
        else:
            self.sendPacket(MSG_KEX_DH_GEX_REQUEST_OLD, '\x00\x00\x08\x00')

    def ssh_KEX_DH_GEX_GROUP(self, packet):
        if self.kexAlg == 'diffie-hellman-group1-sha1':
            pubKey, packet = getNS(packet)
#            print repr(pubKey)
            f, packet = getMP(packet)
            signature, packet = getNS(packet)
            serverKey = keys.getPublicKeyObject(data=pubKey)
            fingerprint = ':'.join(map(lambda c:'%02x'%ord(c),md5.new(pubKey).digest()))
            sharedSecret = MP(pow(f, self.x, DH_PRIME))
            if not self.checkFingerprint(fingerprint):
                self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, 'bad fingerprint')
                return
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
            #print 'hash', h.hexdigest()
            keys.printKey(serverKey)
            if not keys.verifySignature(serverKey, signature, exchangeHash):
                self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, 'bad signature')
                return
            #print "woo we've got keyness"
            self._keySetup(sharedSecret, exchangeHash)
            return
        self.p, rest = getMP(packet)
        self.g, rest = getMP(rest)
        self.x = Util.number.getRandomNumber(512, open('/dev/random').read)
        self.DHpubKey = pow(self.g, self.x, self.p)
        self.sendPacket(MSG_KEX_DH_GEX_INIT, MP(self.DHpubKey))

    def ssh_KEX_DH_GEX_REPLY(self, packet):
        pubKey, packet = getNS(packet)
        f, packet = getMP(packet)
        signature, packet = getNS(packet)
        serverKey = keys.getPublicKeyObject(data = pubKey)
        sharedSecret = MP(pow(f, self.x, self.p))
        fingerprint = ':'.join(map(lambda c:'%02x'%ord(c),md5.new(pubKey).digest()))
        if not self.checkFingerprint(fingerprint):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, 'bad fingerprint')
            return
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
        #print 'hash', h.hexdigest()
        keys.printKey(serverKey)
        if not keys.verifySignature(serverKey, signature, exchangeHash):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED, 'bad signature')
            return
        #print "woo we've got keyness"
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
        #print 'set ciphers'

    def _getKey(self, c, sharedSecret, exchangeHash):
        k1 = sha.new(sharedSecret+exchangeHash+c+self.sessionID).digest()
        k2 = sha.new(sharedSecret+exchangeHash+k1).digest()
        return k1+k2

    def ssh_NEWKEYS(self, packet):
        self.currentEncryptions = self.nextEncryptions
        if self.outgoingCompressionType == 'zlib':
            self.outgoingCompression = zlib.compressobj(6)
            #self.outgoingCompression.compress = lambda x: self.outgoingCompression.compress(x) + self.outgoingCompression.flush(zlib.Z_SYNC_FLUSH)
        if self.incomingCompressionType == 'zlib':
            self.incomingCompression = zlib.decompressobj()
        self.connectionSecure()

    def ssh_SERVICE_ACCEPT(self, packet):
        self.setService(self.instance)

    def requestService(self, instance):
        self.sendPacket(MSG_SERVICE_REQUEST, NS(instance.name))
        self.instance = instance
        
    # client methods
    def checkFingerprint(self, fingerprint):
        # return 1 if it's good
        print 'got server fingerprint', fingerprint
        return 1

    def connectionSecure(self):
        raise NotImplementedError

class SSHCiphers:
    cipherMap = {
        '3des-cbc':('DES3', 24),
        'blowfish-cbc':('Blowfish', 16),
        'aes256-cbc':('AES', 32),
        'aes192-cbc':('AES', 24),
        'aes128-cbc':('AES', 16),
        'arcfour':('ARC4', 16),
        'idea-cbc':('IDEA', 16),
        'cast128-cbc':('CAST', 16),
#        'none':None,
    }
    macMap = {
        'hmac-sha1':'sha',
        'hmac-md5':'md5',
#        'none':None,
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
        self.verify_digest_size = self.inMAC.digest_size

    def _getCipher(self, cip, iv, key):
        modName, keySize = self.cipherMap[cip]
        if not modName: return # no cipher
        mod = __import__('Crypto.Cipher.%s' % modName, {}, {}, 'x')
        return mod.new(key[:keySize], mod.MODE_CBC, iv[:mod.block_size])

    def _getMAC(self, mac, key):
        modName = self.macMap[mac]
        if not modName: return
        mod = __import__(modName, {}, {}, '')
        if not hasattr(mod, 'digest_size'):
            ds=len(mod.new().digest())
        else:
            ds=mod.digest_size
        return HMAC.new(key[:ds], digestmod=mod)

    def encrypt(self, blocks):
        return self.outCip.encrypt(blocks)

    def decrypt(self, blocks):
        return self.inCip.decrypt(blocks)

    def makeMAC(self, seqid, data):
        c = self.outMAC.copy()
        c.update(struct.pack('>L', seqid))
        c.update(data)
        return c.digest()

    def verify(self, seqid, data, mac):
        c = self.inMAC.copy()
        c.update(struct.pack('>L', seqid))
        c.update(data)
        return mac == c.digest()

def buffer_dump(b):
    r=''
    while b:
        c, b = b[:16], b[16:]
        while c:
            a, c = c[:2], c[2:]
            if len(a)==2:
                r=r+'%02x%02x ' % (ord(a[0]), ord(a[1]))
            else:
                r=r+ '%02x' % ord(a[0])
        r=r+'\n'
    return r
        
DH_PRIME = 179769313486231590770839156793787453197860296048756011706444423684197180216158519368947833795864925541502180565485980503646440548199239100050792877003355816639229553136239076508735759914822574862575007425302077447712589550957937778424442426617334727629299387668709205606050270810842907692932019128194467627007L
DH_GENERATOR = 2
   
MSG_DISCONNECT           = 1
MSG_IGNORE               = 2
MSG_UNIMPLEMENTED        = 3
MSG_DEBUG                = 4
MSG_SERVICE_REQUEST      = 5
MSG_SERVICE_ACCEPT       = 6
MSG_KEXINIT              = 20
MSG_NEWKEYS              = 21
MSG_KEXDH_INIT           = 30
MSG_KEXDH_REPLY          = 31
MSG_KEX_DH_GEX_REQUEST_OLD= 30
MSG_KEX_DH_GEX_REQUEST    = 34
MSG_KEX_DH_GEX_GROUP      = 31
MSG_KEX_DH_GEX_INIT       = 32
MSG_KEX_DH_GEX_REPLY      = 33

DISCONNECT_HOST_NOT_ALLOWED_TO_CONNECT    = 1
DISCONNECT_PROTOCOL_ERROR                 = 2
DISCONNECT_KEY_EXCHANGE_FAILED            = 3
DISCONNECT_RESERVED                       = 4
DISCONNECT_MAC_ERROR                      = 5
DISCONNECT_COMPRESSION_ERROR              = 6
DISCONNECT_SERVICE_NOT_AVAILABLE          = 7
DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED = 8
DISCONNECT_HOST_KEY_NOT_VERIFIABLE        = 9
DISCONNECT_CONNECTION_LOST                =10
DISCONNECT_BY_APPLICATION                 =11
DISCONNECT_TOO_MANY_CONNECTIONS           =12
DISCONNECT_AUTH_CANCELLED_BY_USER         =13
DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE =14
DISCONNECT_ILLEGAL_USER_NAME              =15

messages = {}
import transport
for v in dir(transport):
    if v[:4]=='MSG_':
        messages[getattr(transport,v)] = v # doesn't handle doubles
