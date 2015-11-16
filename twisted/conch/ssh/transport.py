# -*- test-case-name: twisted.conch.test.test_transport -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The lowest level SSH protocol.  This handles the key negotiation, the
encryption and the compression.  The transport layer is described in
RFC 4253.

Maintainer: Paul Swartz
"""

# base library imports
import struct
import zlib
import array
from hashlib import md5, sha1, sha256, sha512
import string
import hmac

# external library imports
from Crypto import Util

# twisted imports
from twisted.internet import protocol, defer

from twisted.python import log, randbytes


# sibling imports
from twisted.conch.ssh import address, _kex, keys
from twisted.conch.ssh.common import NS, getNS, MP, getMP, _MPpow, ffs


def _getRandomNumber(random, bits):
    """
    Generate a random number in the range [0, 2 ** bits).

    @param bits: The number of bits in the result.
    @type bits: C{int}

    @rtype: C{int} or C{long}
    @return: The newly generated random number.

    @raise ValueError: if C{bits} is not a multiple of 8.
    """
    if bits % 8:
        raise ValueError("bits (%d) must be a multiple of 8" % (bits,))
    bytes = random(bits / 8)
    result = Util.number.bytes_to_long(bytes)
    return result



def _generateX(random, bits):
    """
    Generate a new value for the private key x.

    From RFC 2631, section 2.2::

        X9.42 requires that the private key x be in the interval
        [2, (q - 2)].  x should be randomly generated in this interval.
    """
    while True:
        x = _getRandomNumber(random, bits)
        if 2 <= x <= (2 ** bits) - 2:
            return x


class _MACParams(tuple):
    """
    L{_MACParams} represents the parameters necessary to compute SSH MAC
    (Message Authenticate Codes).

    L{_MACParams} is a L{tuple} subclass to maintain compatibility with older
    versions of the code.  The elements of a L{_MACParams} are::

        0. The digest object used for the MAC
        1. The inner pad ("ipad") string
        2. The outer pad ("opad") string
        3. The size of the digest produced by the digest object

    L{_MACParams} is also an object lesson in why tuples are a bad type for
    public APIs.

    @ivar key: The HMAC key which will be used.
    """


class SSHTransportBase(protocol.Protocol):
    """
    Protocol supporting basic SSH functionality: sending/receiving packets
    and message dispatch.  To connect to or run a server, you must use
    SSHClientTransport or SSHServerTransport.

    @ivar protocolVersion: A string representing the version of the SSH
        protocol we support.  Currently defaults to '2.0'.

    @ivar version: A string representing the version of the server or client.
        Currently defaults to 'Twisted'.

    @ivar comment: An optional string giving more information about the
        server or client.

    @ivar supportedCiphers: A list of strings representing the encryption
        algorithms supported, in order from most-preferred to least.

    @ivar supportedMACs: A list of strings representing the message
        authentication codes (hashes) supported, in order from most-preferred
        to least.  Both this and supportedCiphers can include 'none' to use
        no encryption or authentication, but that must be done manually,

    @ivar supportedKeyExchanges: A list of strings representing the
        key exchanges supported, in order from most-preferred to least.

    @ivar supportedPublicKeys:  A list of strings representing the
        public key types supported, in order from most-preferred to least.

    @ivar supportedCompressions: A list of strings representing compression
        types supported, from most-preferred to least.

    @ivar supportedLanguages: A list of strings representing languages
        supported, from most-preferred to least.

    @ivar supportedVersions: A container of strings representing supported ssh
        protocol version numbers.

    @ivar isClient: A boolean indicating whether this is a client or server.

    @ivar gotVersion: A boolean indicating whether we have received the
        version string from the other side.

    @ivar buf: Data we've received but hasn't been parsed into a packet.

    @ivar outgoingPacketSequence: the sequence number of the next packet we
        will send.

    @ivar incomingPacketSequence: the sequence number of the next packet we
        are expecting from the other side.

    @ivar outgoingCompression: an object supporting the .compress(str) and
        .flush() methods, or None if there is no outgoing compression.  Used to
        compress outgoing data.

    @ivar outgoingCompressionType: A string representing the outgoing
        compression type.

    @ivar incomingCompression: an object supporting the .decompress(str)
        method, or None if there is no incoming compression.  Used to
        decompress incoming data.

    @ivar incomingCompressionType: A string representing the incoming
        compression type.

    @ivar ourVersionString: the version string that we sent to the other side.
        Used in the key exchange.

    @ivar otherVersionString: the version string sent by the other side.  Used
        in the key exchange.

    @ivar ourKexInitPayload: the MSG_KEXINIT payload we sent.  Used in the key
        exchange.

    @ivar otherKexInitPayload: the MSG_KEXINIT payload we received.  Used in
        the key exchange

    @ivar sessionID: a string that is unique to this SSH session.  Created as
        part of the key exchange, sessionID is used to generate the various
        encryption and authentication keys.

    @ivar service: an SSHService instance, or None.  If it's set to an object,
        it's the currently running service.

    @ivar kexAlg: the agreed-upon key exchange algorithm.

    @ivar keyAlg: the agreed-upon public key type for the key exchange.

    @ivar currentEncryptions: an SSHCiphers instance.  It represents the
        current encryption and authentication options for the transport.

    @ivar nextEncryptions: an SSHCiphers instance.  Held here until the
        MSG_NEWKEYS messages are exchanged, when nextEncryptions is
        transitioned to currentEncryptions.

    @ivar first: the first bytes of the next packet.  In order to avoid
        decrypting data twice, the first bytes are decrypted and stored until
        the whole packet is available.

    @ivar _keyExchangeState: The current protocol state with respect to key
        exchange.  This is either C{_KEY_EXCHANGE_NONE} if no key exchange is
        in progress (and returns to this value after any key exchange
        completqes), C{_KEY_EXCHANGE_REQUESTED} if this side of the connection
        initiated a key exchange, and C{_KEY_EXCHANGE_PROGRESSING} if the other
        side of the connection initiated a key exchange.  C{_KEY_EXCHANGE_NONE}
        is the initial value (however SSH connections begin with key exchange,
        so it will quickly change to another state).

    @ivar _blockedByKeyExchange: Whenever C{_keyExchangeState} is not
        C{_KEY_EXCHANGE_NONE}, this is a C{list} of pending messages which were
        passed to L{sendPacket} but could not be sent because it is not legal
        to send them while a key exchange is in progress.  When the key
        exchange completes, another attempt is made to send these messages.
    """


    protocolVersion = '2.0'
    version = 'Twisted'
    comment = ''
    ourVersionString = ('SSH-' + protocolVersion + '-' + version + ' '
            + comment).strip()

    # C{none} is supported as cipher and hmac. For security they are disabled
    # by default. To enable them, subclass this class and add it, or do:
    # SSHTransportBase.supportedCiphers.append('none')
    # List ordered by preference.
    supportedCiphers = ['aes256-ctr', 'aes256-cbc', 'aes192-ctr', 'aes192-cbc',
                        'aes128-ctr', 'aes128-cbc', 'cast128-ctr',
                        'cast128-cbc', 'blowfish-ctr', 'blowfish-cbc',
                        '3des-ctr', '3des-cbc'] # ,'none']
    supportedMACs = [
        'hmac-sha2-512',
        'hmac-sha2-256',
        'hmac-sha1',
        'hmac-md5',
        # `none`,
        ]

    supportedKeyExchanges = _kex.getSupportedKeyExchanges()
    supportedPublicKeys = ['ssh-rsa', 'ssh-dss']
    supportedCompressions = ['none', 'zlib']
    supportedLanguages = ()
    supportedVersions = ('1.99', '2.0')
    isClient = False
    gotVersion = False
    buf = ''
    outgoingPacketSequence = 0
    incomingPacketSequence = 0
    outgoingCompression = None
    incomingCompression = None
    sessionID = None
    service = None

    # There is no key exchange activity in progress.
    _KEY_EXCHANGE_NONE = '_KEY_EXCHANGE_NONE'

    # Key exchange is in progress and we started it.
    _KEY_EXCHANGE_REQUESTED = '_KEY_EXCHANGE_REQUESTED'

    # Key exchange is in progress and both sides have sent KEXINIT messages.
    _KEY_EXCHANGE_PROGRESSING = '_KEY_EXCHANGE_PROGRESSING'

    # There is a fourth conceptual state not represented here: KEXINIT received
    # but not sent.  Since we always send a KEXINIT as soon as we get it, we
    # can't ever be in that state.

    # The current key exchange state.
    _keyExchangeState = _KEY_EXCHANGE_NONE
    _blockedByKeyExchange = None

    def connectionLost(self, reason):
        if self.service:
            self.service.serviceStopped()
        if hasattr(self, 'avatar'):
            self.logoutFunction()
        log.msg('connection lost')


    def connectionMade(self):
        """
        Called when the connection is made to the other side.  We sent our
        version and the MSG_KEXINIT packet.
        """
        self.transport.write('%s\r\n' % (self.ourVersionString,))
        self.currentEncryptions = SSHCiphers('none', 'none', 'none', 'none')
        self.currentEncryptions.setKeys('', '', '', '', '', '')
        self.sendKexInit()


    def sendKexInit(self):
        """
        Send a I{KEXINIT} message to initiate key exchange or to respond to a
        key exchange initiated by the peer.

        @raise RuntimeError: If a key exchange has already been started and it
            is not appropriate to send a I{KEXINIT} message at this time.

        @return: C{None}
        """
        if self._keyExchangeState != self._KEY_EXCHANGE_NONE:
            raise RuntimeError(
                "Cannot send KEXINIT while key exchange state is %r" % (
                    self._keyExchangeState,))

        self.ourKexInitPayload = (chr(MSG_KEXINIT) +
               randbytes.secureRandom(16) +
               NS(','.join(self.supportedKeyExchanges)) +
               NS(','.join(self.supportedPublicKeys)) +
               NS(','.join(self.supportedCiphers)) +
               NS(','.join(self.supportedCiphers)) +
               NS(','.join(self.supportedMACs)) +
               NS(','.join(self.supportedMACs)) +
               NS(','.join(self.supportedCompressions)) +
               NS(','.join(self.supportedCompressions)) +
               NS(','.join(self.supportedLanguages)) +
               NS(','.join(self.supportedLanguages)) +
               '\000' + '\000\000\000\000')
        self.sendPacket(MSG_KEXINIT, self.ourKexInitPayload[1:])
        self._keyExchangeState = self._KEY_EXCHANGE_REQUESTED
        self._blockedByKeyExchange = []


    def _allowedKeyExchangeMessageType(self, messageType):
        """
        Determine if the given message type may be sent while key exchange is
        in progress.

        @param messageType: The type of message
        @type messageType: C{int}

        @return: C{True} if the given type of message may be sent while key
            exchange is in progress, C{False} if it may not.
        @rtype: C{bool}

        @see: U{http://tools.ietf.org/html/rfc4253#section-7.1}
        """
        # Written somewhat peculularly to reflect the way the specification
        # defines the allowed message types.
        if 1 <= messageType <= 19:
            return messageType not in (MSG_SERVICE_REQUEST, MSG_SERVICE_ACCEPT)
        if 20 <= messageType <= 29:
            return messageType not in (MSG_KEXINIT,)
        return 30 <= messageType <= 49


    def sendPacket(self, messageType, payload):
        """
        Sends a packet.  If it's been set up, compress the data, encrypt it,
        and authenticate it before sending.  If key exchange is in progress and
        the message is not part of key exchange, queue it to be sent later.

        @param messageType: The type of the packet; generally one of the
                            MSG_* values.
        @type messageType: C{int}
        @param payload: The payload for the message.
        @type payload: C{str}
        """
        if self._keyExchangeState != self._KEY_EXCHANGE_NONE:
            if not self._allowedKeyExchangeMessageType(messageType):
                self._blockedByKeyExchange.append((messageType, payload))
                return

        payload = chr(messageType) + payload
        if self.outgoingCompression:
            payload = (self.outgoingCompression.compress(payload)
                       + self.outgoingCompression.flush(2))
        bs = self.currentEncryptions.encBlockSize
        # 4 for the packet length and 1 for the padding length
        totalSize = 5 + len(payload)
        lenPad = bs - (totalSize % bs)
        if lenPad < 4:
            lenPad = lenPad + bs
        packet = (struct.pack('!LB',
                              totalSize + lenPad - 4, lenPad) +
                  payload + randbytes.secureRandom(lenPad))
        encPacket = (
            self.currentEncryptions.encrypt(packet) +
            self.currentEncryptions.makeMAC(
                self.outgoingPacketSequence, packet))
        self.transport.write(encPacket)
        self.outgoingPacketSequence += 1


    def getPacket(self):
        """
        Try to return a decrypted, authenticated, and decompressed packet
        out of the buffer.  If there is not enough data, return None.

        @rtype: C{str}/C{None}
        """
        bs = self.currentEncryptions.decBlockSize
        ms = self.currentEncryptions.verifyDigestSize
        if len(self.buf) < bs: return # not enough data
        if not hasattr(self, 'first'):
            first = self.currentEncryptions.decrypt(self.buf[:bs])
        else:
            first = self.first
            del self.first
        packetLen, paddingLen = struct.unpack('!LB', first[:5])
        if packetLen > 1048576: # 1024 ** 2
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR,
                                'bad packet length %s' % packetLen)
            return
        if len(self.buf) < packetLen + 4 + ms:
            self.first = first
            return # not enough packet
        if(packetLen + 4) % bs != 0:
            self.sendDisconnect(
                DISCONNECT_PROTOCOL_ERROR,
                'bad packet mod (%i%%%i == %i)' % (packetLen + 4, bs,
                                                   (packetLen + 4) % bs))
            return
        encData, self.buf = self.buf[:4 + packetLen], self.buf[4 + packetLen:]
        packet = first + self.currentEncryptions.decrypt(encData[bs:])
        if len(packet) != 4 + packetLen:
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR,
                                'bad decryption')
            return
        if ms:
            macData, self.buf = self.buf[:ms], self.buf[ms:]
            if not self.currentEncryptions.verify(self.incomingPacketSequence,
                                                  packet, macData):
                self.sendDisconnect(DISCONNECT_MAC_ERROR, 'bad MAC')
                return
        payload = packet[5:-paddingLen]
        if self.incomingCompression:
            try:
                payload = self.incomingCompression.decompress(payload)
            except: # bare except, because who knows what kind of errors
                    # decompression can raise
                log.err()
                self.sendDisconnect(DISCONNECT_COMPRESSION_ERROR,
                                    'compression error')
                return
        self.incomingPacketSequence += 1
        return payload


    def _unsupportedVersionReceived(self, remoteVersion):
        """
        Called when an unsupported version of the ssh protocol is received from
        the remote endpoint.

        @param remoteVersion: remote ssh protocol version which is unsupported
            by us.
        @type remoteVersion: C{str}
        """
        self.sendDisconnect(DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED,
            'bad version ' + remoteVersion)


    def dataReceived(self, data):
        """
        First, check for the version string (SSH-2.0-*).  After that has been
        received, this method adds data to the buffer, and pulls out any
        packets.

        @type data: C{str}
        """
        self.buf = self.buf + data
        if not self.gotVersion:
            if self.buf.find('\n', self.buf.find('SSH-')) == -1:
                return
            lines = self.buf.split('\n')
            for p in lines:
                if p.startswith('SSH-'):
                    self.gotVersion = True
                    self.otherVersionString = p.strip()
                    remoteVersion = p.split('-')[1]
                    if remoteVersion not in self.supportedVersions:
                        self._unsupportedVersionReceived(remoteVersion)
                        return
                    i = lines.index(p)
                    self.buf = '\n'.join(lines[i + 1:])
        packet = self.getPacket()
        while packet:
            messageNum = ord(packet[0])
            self.dispatchMessage(messageNum, packet[1:])
            packet = self.getPacket()


    def dispatchMessage(self, messageNum, payload):
        """
        Send a received message to the appropriate method.

        @type messageNum: C{int}
        @type payload: c{str}
        """
        if messageNum < 50 and messageNum in messages:
            messageType = messages[messageNum][4:]
            f = getattr(self, 'ssh_%s' % messageType, None)
            if f is not None:
                f(payload)
            else:
                log.msg("couldn't handle %s" % messageType)
                log.msg(repr(payload))
                self.sendUnimplemented()
        elif self.service:
            log.callWithLogger(self.service, self.service.packetReceived,
                               messageNum, payload)
        else:
            log.msg("couldn't handle %s" % messageNum)
            log.msg(repr(payload))
            self.sendUnimplemented()

    def getPeer(self):
        """
        Returns an L{SSHTransportAddress} corresponding to the other (peer)
        side of this transport.

        @return: L{SSHTransportAddress} for the peer
        @rtype: L{SSHTransportAddress}
        @since: 12.1
        """
        return address.SSHTransportAddress(self.transport.getPeer())

    def getHost(self):
        """
        Returns an L{SSHTransportAddress} corresponding to the this side of
        transport.

        @return: L{SSHTransportAddress} for the peer
        @rtype: L{SSHTransportAddress}
        @since: 12.1
        """
        return address.SSHTransportAddress(self.transport.getHost())


    @property
    def kexAlg(self):
        """
        The key exchange algorithm name agreed between client and server.
        """
        return self._kexAlg


    @kexAlg.setter
    def kexAlg(self, value):
        """
        Set the key exchange algorithm name.

        @raises ConchError: if the key exchange algorithm is not found.
        """
        # Check for supportedness.
        _kex.getKex(value)
        self._kexAlg = value


    # Client-initiated rekeying looks like this:
    #
    #  C> MSG_KEXINIT
    #  S> MSG_KEXINIT
    #  C> MSG_KEX_DH_GEX_REQUEST  or   MSG_KEXDH_INIT
    #  S> MSG_KEX_DH_GEX_GROUP    or   MSG_KEXDH_REPLY
    #  C> MSG_KEX_DH_GEX_INIT     or   --
    #  S> MSG_KEX_DH_GEX_REPLY    or   --
    #  C> MSG_NEWKEYS
    #  S> MSG_NEWKEYS
    #
    # Server-initiated rekeying is the same, only the first two messages are
    # switched.

    def ssh_KEXINIT(self, packet):
        """
        Called when we receive a MSG_KEXINIT message.  Payload::
            bytes[16] cookie
            string keyExchangeAlgorithms
            string keyAlgorithms
            string incomingEncryptions
            string outgoingEncryptions
            string incomingAuthentications
            string outgoingAuthentications
            string incomingCompressions
            string outgoingCompressions
            string incomingLanguages
            string outgoingLanguages
            bool firstPacketFollows
            unit32 0 (reserved)

        Starts setting up the key exchange, keys, encryptions, and
        authentications.  Extended by ssh_KEXINIT in SSHServerTransport and
        SSHClientTransport.
        """
        self.otherKexInitPayload = chr(MSG_KEXINIT) + packet
        #cookie = packet[: 16] # taking this is useless
        k = getNS(packet[16:], 10)
        strings, rest = k[:-1], k[-1]
        (kexAlgs, keyAlgs, encCS, encSC, macCS, macSC, compCS, compSC, langCS,
         langSC) = [s.split(',') for s in strings]
        # these are the server directions
        outs = [encSC, macSC, compSC]
        ins = [encCS, macSC, compCS]
        if self.isClient:
            outs, ins = ins, outs # switch directions
        server = (self.supportedKeyExchanges, self.supportedPublicKeys,
                self.supportedCiphers, self.supportedCiphers,
                self.supportedMACs, self.supportedMACs,
                self.supportedCompressions, self.supportedCompressions)
        client = (kexAlgs, keyAlgs, outs[0], ins[0], outs[1], ins[1],
                outs[2], ins[2])
        if self.isClient:
            server, client = client, server
        self.kexAlg = ffs(client[0], server[0])
        self.keyAlg = ffs(client[1], server[1])
        self.nextEncryptions = SSHCiphers(
            ffs(client[2], server[2]),
            ffs(client[3], server[3]),
            ffs(client[4], server[4]),
            ffs(client[5], server[5]))
        self.outgoingCompressionType = ffs(client[6], server[6])
        self.incomingCompressionType = ffs(client[7], server[7])
        if None in (self.kexAlg, self.keyAlg, self.outgoingCompressionType,
                    self.incomingCompressionType):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED,
                                "couldn't match all kex parts")
            return
        if None in self.nextEncryptions.__dict__.values():
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED,
                                "couldn't match all kex parts")
            return
        log.msg('kex alg, key alg: %s %s' % (self.kexAlg, self.keyAlg))
        log.msg('outgoing: %s %s %s' % (self.nextEncryptions.outCipType,
                                        self.nextEncryptions.outMACType,
                                        self.outgoingCompressionType))
        log.msg('incoming: %s %s %s' % (self.nextEncryptions.inCipType,
                                        self.nextEncryptions.inMACType,
                                        self.incomingCompressionType))

        if self._keyExchangeState == self._KEY_EXCHANGE_REQUESTED:
            self._keyExchangeState = self._KEY_EXCHANGE_PROGRESSING
        else:
            self.sendKexInit()

        return kexAlgs, keyAlgs, rest # for SSHServerTransport to use


    def ssh_DISCONNECT(self, packet):
        """
        Called when we receive a MSG_DISCONNECT message.  Payload::
            long code
            string description

        This means that the other side has disconnected.  Pass the message up
        and disconnect ourselves.
        """
        reasonCode = struct.unpack('>L', packet[: 4])[0]
        description, foo = getNS(packet[4:])
        self.receiveError(reasonCode, description)
        self.transport.loseConnection()


    def ssh_IGNORE(self, packet):
        """
        Called when we receive a MSG_IGNORE message.  No payload.
        This means nothing; we simply return.
        """


    def ssh_UNIMPLEMENTED(self, packet):
        """
        Called when we receive a MSG_UNIMPLEMENTED message.  Payload::
            long packet

        This means that the other side did not implement one of our packets.
        """
        seqnum, = struct.unpack('>L', packet)
        self.receiveUnimplemented(seqnum)


    def ssh_DEBUG(self, packet):
        """
        Called when we receive a MSG_DEBUG message.  Payload::
            bool alwaysDisplay
            string message
            string language

        This means the other side has passed along some debugging info.
        """
        alwaysDisplay = bool(packet[0])
        message, lang, foo = getNS(packet[1:], 2)
        self.receiveDebug(alwaysDisplay, message, lang)


    def setService(self, service):
        """
        Set our service to service and start it running.  If we were
        running a service previously, stop it first.

        @type service: C{SSHService}
        """
        log.msg('starting service %s' % service.name)
        if self.service:
            self.service.serviceStopped()
        self.service = service
        service.transport = self
        self.service.serviceStarted()


    def sendDebug(self, message, alwaysDisplay=False, language=''):
        """
        Send a debug message to the other side.

        @param message: the message to send.
        @type message: C{str}
        @param alwaysDisplay: if True, tell the other side to always
                              display this message.
        @type alwaysDisplay: C{bool}
        @param language: optionally, the language the message is in.
        @type language: C{str}
        """
        self.sendPacket(MSG_DEBUG, chr(alwaysDisplay) + NS(message) +
                        NS(language))


    def sendIgnore(self, message):
        """
        Send a message that will be ignored by the other side.  This is
        useful to fool attacks based on guessing packet sizes in the
        encrypted stream.

        @param message: data to send with the message
        @type message: C{str}
        """
        self.sendPacket(MSG_IGNORE, NS(message))


    def sendUnimplemented(self):
        """
        Send a message to the other side that the last packet was not
        understood.
        """
        seqnum = self.incomingPacketSequence
        self.sendPacket(MSG_UNIMPLEMENTED, struct.pack('!L', seqnum))


    def sendDisconnect(self, reason, desc):
        """
        Send a disconnect message to the other side and then disconnect.

        @param reason: the reason for the disconnect.  Should be one of the
                       DISCONNECT_* values.
        @type reason: C{int}
        @param desc: a descrption of the reason for the disconnection.
        @type desc: C{str}
        """
        self.sendPacket(
            MSG_DISCONNECT, struct.pack('>L', reason) + NS(desc) + NS(''))
        log.msg('Disconnecting with error, code %s\nreason: %s' % (reason,
                                                                   desc))
        self.transport.loseConnection()


    def _getKey(self, c, sharedSecret, exchangeHash):
        """
        Get one of the keys for authentication/encryption.

        @type c: C{str}
        @type sharedSecret: C{str}
        @type exchangeHash: C{str}
        """
        hashProcessor = _kex.getHashProcessor(self.kexAlg)
        k1 = hashProcessor(sharedSecret + exchangeHash + c + self.sessionID)
        k1 = k1.digest()
        k2 = hashProcessor(sharedSecret + exchangeHash + k1).digest()
        return k1 + k2


    def _keySetup(self, sharedSecret, exchangeHash):
        """
        Set up the keys for the connection and sends MSG_NEWKEYS when
        finished,

        @param sharedSecret: a secret string agreed upon using a Diffie-
                             Hellman exchange, so it is only shared between
                             the server and the client.
        @type sharedSecret: C{str}
        @param exchangeHash: A hash of various data known by both sides.
        @type exchangeHash: C{str}
        """
        if not self.sessionID:
            self.sessionID = exchangeHash
        initIVCS = self._getKey('A', sharedSecret, exchangeHash)
        initIVSC = self._getKey('B', sharedSecret, exchangeHash)
        encKeyCS = self._getKey('C', sharedSecret, exchangeHash)
        encKeySC = self._getKey('D', sharedSecret, exchangeHash)
        integKeyCS = self._getKey('E', sharedSecret, exchangeHash)
        integKeySC = self._getKey('F', sharedSecret, exchangeHash)
        outs = [initIVSC, encKeySC, integKeySC]
        ins = [initIVCS, encKeyCS, integKeyCS]
        if self.isClient: # reverse for the client
            log.msg('REVERSE')
            outs, ins = ins, outs
        self.nextEncryptions.setKeys(outs[0], outs[1], ins[0], ins[1],
                                     outs[2], ins[2])
        self.sendPacket(MSG_NEWKEYS, '')


    def _newKeys(self):
        """
        Called back by a subclass once a I{MSG_NEWKEYS} message has been
        received.  This indicates key exchange has completed and new encryption
        and compression parameters should be adopted.  Any messages which were
        queued during key exchange will also be flushed.
        """
        log.msg('NEW KEYS')
        self.currentEncryptions = self.nextEncryptions
        if self.outgoingCompressionType == 'zlib':
            self.outgoingCompression = zlib.compressobj(6)
        if self.incomingCompressionType == 'zlib':
            self.incomingCompression = zlib.decompressobj()

        self._keyExchangeState = self._KEY_EXCHANGE_NONE
        messages = self._blockedByKeyExchange
        self._blockedByKeyExchange = None
        for (messageType, payload) in messages:
            self.sendPacket(messageType, payload)


    def isEncrypted(self, direction="out"):
        """
        Return True if the connection is encrypted in the given direction.
        Direction must be one of ["out", "in", "both"].
        """
        if direction == "out":
            return self.currentEncryptions.outCipType != 'none'
        elif direction == "in":
            return self.currentEncryptions.inCipType != 'none'
        elif direction == "both":
            return self.isEncrypted("in") and self.isEncrypted("out")
        else:
            raise TypeError('direction must be "out", "in", or "both"')


    def isVerified(self, direction="out"):
        """
        Return True if the connecction is verified/authenticated in the
        given direction.  Direction must be one of ["out", "in", "both"].
        """
        if direction == "out":
            return self.currentEncryptions.outMACType != 'none'
        elif direction == "in":
            return self.currentEncryptions.inMACType != 'none'
        elif direction == "both":
            return self.isVerified("in")and self.isVerified("out")
        else:
            raise TypeError('direction must be "out", "in", or "both"')


    def loseConnection(self):
        """
        Lose the connection to the other side, sending a
        DISCONNECT_CONNECTION_LOST message.
        """
        self.sendDisconnect(DISCONNECT_CONNECTION_LOST,
                            "user closed connection")


    # client methods
    def receiveError(self, reasonCode, description):
        """
        Called when we receive a disconnect error message from the other
        side.

        @param reasonCode: the reason for the disconnect, one of the
                           DISCONNECT_ values.
        @type reasonCode: C{int}
        @param description: a human-readable description of the
                            disconnection.
        @type description: C{str}
        """
        log.msg('Got remote error, code %s\nreason: %s' % (reasonCode,
                                                           description))


    def receiveUnimplemented(self, seqnum):
        """
        Called when we receive an unimplemented packet message from the other
        side.

        @param seqnum: the sequence number that was not understood.
        @type seqnum: C{int}
        """
        log.msg('other side unimplemented packet #%s' % seqnum)


    def receiveDebug(self, alwaysDisplay, message, lang):
        """
        Called when we receive a debug message from the other side.

        @param alwaysDisplay: if True, this message should always be
                              displayed.
        @type alwaysDisplay: C{bool}
        @param message: the debug message
        @type message: C{str}
        @param lang: optionally the language the message is in.
        @type lang: C{str}
        """
        if alwaysDisplay:
            log.msg('Remote Debug Message: %s' % message)



class SSHServerTransport(SSHTransportBase):
    """
    SSHServerTransport implements the server side of the SSH protocol.

    @ivar isClient: since we are never the client, this is always False.

    @ivar ignoreNextPacket: if True, ignore the next key exchange packet.  This
        is set when the client sends a guessed key exchange packet but with
        an incorrect guess.

    @ivar dhGexRequest: the KEX_DH_GEX_REQUEST(_OLD) that the client sent.
        The key generation needs this to be stored.

    @ivar g: the Diffie-Hellman group generator.

    @ivar p: the Diffie-Hellman group prime.
    """
    isClient = False
    ignoreNextPacket = 0


    def ssh_KEXINIT(self, packet):
        """
        Called when we receive a MSG_KEXINIT message.  For a description
        of the packet, see SSHTransportBase.ssh_KEXINIT().  Additionally,
        this method checks if a guessed key exchange packet was sent.  If
        it was sent, and it guessed incorrectly, the next key exchange
        packet MUST be ignored.
        """
        retval = SSHTransportBase.ssh_KEXINIT(self, packet)
        if not retval: # disconnected
            return
        else:
            kexAlgs, keyAlgs, rest = retval
        if ord(rest[0]): # first_kex_packet_follows
            if (kexAlgs[0] != self.supportedKeyExchanges[0] or
                keyAlgs[0] != self.supportedPublicKeys[0]):
                self.ignoreNextPacket = True # guess was wrong


    def _ssh_KEXDH_INIT(self, packet):
        """
        Called to handle the beginning of a non-group key exchange.

        Unlike other message types, this is not dispatched automatically.  It
        is called from C{ssh_KEX_DH_GEX_REQUEST_OLD} because an extra check is
        required to determine if this is really a KEXDH_INIT message or if it
        is a KEX_DH_GEX_REQUEST_OLD message.

        The KEXDH_INIT payload::

                integer e (the client's Diffie-Hellman public key)

        We send the KEXDH_REPLY with our host key and signature.
        """
        clientDHpublicKey, foo = getMP(packet)
        y = _getRandomNumber(randbytes.secureRandom, 512)
        self.g, self.p = _kex.getDHGeneratorAndPrime(self.kexAlg)
        serverDHpublicKey = _MPpow(self.g, y, self.p)
        sharedSecret = _MPpow(clientDHpublicKey, y, self.p)
        h = sha1()
        h.update(NS(self.otherVersionString))
        h.update(NS(self.ourVersionString))
        h.update(NS(self.otherKexInitPayload))
        h.update(NS(self.ourKexInitPayload))
        h.update(NS(self.factory.publicKeys[self.keyAlg].blob()))
        h.update(MP(clientDHpublicKey))
        h.update(serverDHpublicKey)
        h.update(sharedSecret)
        exchangeHash = h.digest()
        self.sendPacket(
            MSG_KEXDH_REPLY,
            NS(self.factory.publicKeys[self.keyAlg].blob()) +
            serverDHpublicKey +
            NS(self.factory.privateKeys[self.keyAlg].sign(exchangeHash)))
        self._keySetup(sharedSecret, exchangeHash)


    def ssh_KEX_DH_GEX_REQUEST_OLD(self, packet):
        """
        This represents different key exchange methods that share the same
        integer value.  If the message is determined to be a KEXDH_INIT,
        C{_ssh_KEXDH_INIT} is called to handle it.  Otherwise, for
        KEX_DH_GEX_REQUEST_OLD payload::

                integer ideal (ideal size for the Diffie-Hellman prime)

            We send the KEX_DH_GEX_GROUP message with the group that is
            closest in size to ideal.

        If we were told to ignore the next key exchange packet by ssh_KEXINIT,
        drop it on the floor and return.
        """
        if self.ignoreNextPacket:
            self.ignoreNextPacket = 0
            return

        # KEXDH_INIT and KEX_DH_GEX_REQUEST_OLD have the same value, so use
        # another cue to decide what kind of message the peer sent us.
        if _kex.isFixedGroup(self.kexAlg):
            return self._ssh_KEXDH_INIT(packet)
        else:
            self.dhGexRequest = packet
            ideal = struct.unpack('>L', packet)[0]
            self.g, self.p = self.factory.getDHPrime(ideal)
            self.sendPacket(MSG_KEX_DH_GEX_GROUP, MP(self.p) + MP(self.g))


    def ssh_KEX_DH_GEX_REQUEST(self, packet):
        """
        Called when we receive a MSG_KEX_DH_GEX_REQUEST message.  Payload::
            integer minimum
            integer ideal
            integer maximum

        The client is asking for a Diffie-Hellman group between minimum and
        maximum size, and close to ideal if possible.  We reply with a
        MSG_KEX_DH_GEX_GROUP message.

        If we were told to ignore the next key exchange packet by ssh_KEXINIT,
        drop it on the floor and return.
        """
        if self.ignoreNextPacket:
            self.ignoreNextPacket = 0
            return
        self.dhGexRequest = packet
        min, ideal, max = struct.unpack('>3L', packet)
        self.g, self.p = self.factory.getDHPrime(ideal)
        self.sendPacket(MSG_KEX_DH_GEX_GROUP, MP(self.p) + MP(self.g))


    def ssh_KEX_DH_GEX_INIT(self, packet):
        """
        Called when we get a MSG_KEX_DH_GEX_INIT message.  Payload::
            integer e (client DH public key)

        We send the MSG_KEX_DH_GEX_REPLY message with our host key and
        signature.
        """
        clientDHpublicKey, foo = getMP(packet)
        # TODO: we should also look at the value they send to us and reject
        # insecure values of f (if g==2 and f has a single '1' bit while the
        # rest are '0's, then they must have used a small y also).

        # TODO: This could be computed when self.p is set up
        #  or do as openssh does and scan f for a single '1' bit instead

        pSize = Util.number.size(self.p)
        y = _getRandomNumber(randbytes.secureRandom, pSize)

        serverDHpublicKey = _MPpow(self.g, y, self.p)
        sharedSecret = _MPpow(clientDHpublicKey, y, self.p)
        h = _kex.getHashProcessor(self.kexAlg)()
        h.update(NS(self.otherVersionString))
        h.update(NS(self.ourVersionString))
        h.update(NS(self.otherKexInitPayload))
        h.update(NS(self.ourKexInitPayload))
        h.update(NS(self.factory.publicKeys[self.keyAlg].blob()))
        h.update(self.dhGexRequest)
        h.update(MP(self.p))
        h.update(MP(self.g))
        h.update(MP(clientDHpublicKey))
        h.update(serverDHpublicKey)
        h.update(sharedSecret)
        exchangeHash = h.digest()
        self.sendPacket(
            MSG_KEX_DH_GEX_REPLY,
            NS(self.factory.publicKeys[self.keyAlg].blob()) +
            serverDHpublicKey +
            NS(self.factory.privateKeys[self.keyAlg].sign(exchangeHash)))
        self._keySetup(sharedSecret, exchangeHash)


    def ssh_NEWKEYS(self, packet):
        """
        Called when we get a MSG_NEWKEYS message.  No payload.
        When we get this, the keys have been set on both sides, and we
        start using them to encrypt and authenticate the connection.
        """
        if packet != '':
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR,
                                "NEWKEYS takes no data")
            return
        self._newKeys()


    def ssh_SERVICE_REQUEST(self, packet):
        """
        Called when we get a MSG_SERVICE_REQUEST message.  Payload::
            string serviceName

        The client has requested a service.  If we can start the service,
        start it; otherwise, disconnect with
        DISCONNECT_SERVICE_NOT_AVAILABLE.
        """
        service, rest = getNS(packet)
        cls = self.factory.getService(self, service)
        if not cls:
            self.sendDisconnect(DISCONNECT_SERVICE_NOT_AVAILABLE,
                                "don't have service %s" % service)
            return
        else:
            self.sendPacket(MSG_SERVICE_ACCEPT, NS(service))
            self.setService(cls())



class SSHClientTransport(SSHTransportBase):
    """
    SSHClientTransport implements the client side of the SSH protocol.

    @ivar isClient: since we are always the client, this is always True.

    @ivar _gotNewKeys: if we receive a MSG_NEWKEYS message before we are
        ready to transition to the new keys, this is set to True so we
        can transition when the keys are ready locally.

    @ivar x: our Diffie-Hellman private key.

    @ivar e: our Diffie-Hellman public key.

    @ivar g: the Diffie-Hellman group generator.

    @ivar p: the Diffie-Hellman group prime

    @ivar instance: the SSHService object we are requesting.

    @ivar _dhMinimalGroupSize: Minimal acceptable group size advertised by the
        client in MSG_KEX_DH_GEX_REQUEST.
    @type _dhMinimalGroupSize: int

    @ivar _dhMaximalGroupSize: Maximal acceptable group size advertised by the
        client in MSG_KEX_DH_GEX_REQUEST.
    @type _dhMaximalGroupSize: int

    @ivar _dhPreferredGroupSize: Preferred group size advertised by the client
        in MSG_KEX_DH_GEX_REQUEST.
    @type _dhPreferredGroupSize: int
    """
    isClient = True

    # Recommended minimal and maximal values from RFC 4419, 3.
    _dhMinimalGroupSize = 1024
    _dhMaximalGroupSize = 8192
    # FIXME: https://twistedmatrix.com/trac/ticket/8103
    # This may need to be more dynamic; compare kexgex_client in
    # OpenSSH.
    _dhPreferredGroupSize = 2048

    def connectionMade(self):
        """
        Called when the connection is started with the server.  Just sets
        up a private instance variable.
        """
        SSHTransportBase.connectionMade(self)
        self._gotNewKeys = 0


    def ssh_KEXINIT(self, packet):
        """
        Called when we receive a MSG_KEXINIT message.  For a description
        of the packet, see SSHTransportBase.ssh_KEXINIT().  Additionally,
        this method sends the first key exchange packet.  If the agreed-upon
        exchange has a fixed prime/generator group, generate a public key
        and send it in a MSG_KEXDH_INIT message. Otherwise, ask for a 2048
        bit group with a MSG_KEX_DH_GEX_REQUEST message.
        """
        if SSHTransportBase.ssh_KEXINIT(self, packet) is None:
            # Connection was disconnected while doing base processing.
            # Maybe no common protocols were agreed.
            return

        if _kex.isFixedGroup(self.kexAlg):
            # We agreed on a fixed group key exchange algorithm.
            self.x = _generateX(randbytes.secureRandom, 512)
            self.g, self.p = _kex.getDHGeneratorAndPrime(self.kexAlg)
            self.e = _MPpow(self.g, self.x, self.p)
            self.sendPacket(MSG_KEXDH_INIT, self.e)
        else:
            # We agreed on a dynamic group. Tell the server what range of
            # group sizes we accept, and what size we prefer; the server
            # will then select a group.
            self.sendPacket(
                MSG_KEX_DH_GEX_REQUEST,
                struct.pack(
                    '!LLL',
                    self._dhMinimalGroupSize,
                    self._dhPreferredGroupSize,
                    self._dhMaximalGroupSize,
                    ))


    def _ssh_KEXDH_REPLY(self, packet):
        """
        Called to handle a reply to a non-group key exchange message
        (KEXDH_INIT).

        Like the handler for I{KEXDH_INIT}, this message type has an
        overlapping value.  This method is called from C{ssh_KEX_DH_GEX_GROUP}
        if that method detects a non-group key exchange is in progress.

        Payload::

            string serverHostKey
            integer f (server Diffie-Hellman public key)
            string signature

        We verify the host key by calling verifyHostKey, then continue in
        _continueKEXDH_REPLY.
        """
        pubKey, packet = getNS(packet)
        f, packet = getMP(packet)
        signature, packet = getNS(packet)
        fingerprint = ':'.join([ch.encode('hex') for ch in
                                md5(pubKey).digest()])
        d = self.verifyHostKey(pubKey, fingerprint)
        d.addCallback(self._continueKEXDH_REPLY, pubKey, f, signature)
        d.addErrback(
            lambda unused: self.sendDisconnect(
                DISCONNECT_HOST_KEY_NOT_VERIFIABLE, 'bad host key'))
        return d


    def ssh_KEX_DH_GEX_GROUP(self, packet):
        """
        This handles different messages which share an integer value.

        If the key exchange does not have a fixed prime/generator group,
        we generate a Diffie-Hellman public key and send it in a
        MSG_KEX_DH_GEX_INIT message.

        Payload::
            string g (group generator)
            string p (group prime)
        """
        if _kex.isFixedGroup(self.kexAlg):
            return self._ssh_KEXDH_REPLY(packet)
        else:
            self.p, rest = getMP(packet)
            self.g, rest = getMP(rest)
            self.x = _generateX(randbytes.secureRandom, 320)
            self.e = _MPpow(self.g, self.x, self.p)
            self.sendPacket(MSG_KEX_DH_GEX_INIT, self.e)


    def _continueKEXDH_REPLY(self, ignored, pubKey, f, signature):
        """
        The host key has been verified, so we generate the keys.

        @param pubKey: the public key blob for the server's public key.
        @type pubKey: C{str}
        @param f: the server's Diffie-Hellman public key.
        @type f: C{long}
        @param signature: the server's signature, verifying that it has the
            correct private key.
        @type signature: C{str}
        """
        serverKey = keys.Key.fromString(pubKey)
        sharedSecret = _MPpow(f, self.x, self.p)
        h = sha1()
        h.update(NS(self.ourVersionString))
        h.update(NS(self.otherVersionString))
        h.update(NS(self.ourKexInitPayload))
        h.update(NS(self.otherKexInitPayload))
        h.update(NS(pubKey))
        h.update(self.e)
        h.update(MP(f))
        h.update(sharedSecret)
        exchangeHash = h.digest()
        if not serverKey.verify(signature, exchangeHash):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED,
                                'bad signature')
            return
        self._keySetup(sharedSecret, exchangeHash)


    def ssh_KEX_DH_GEX_REPLY(self, packet):
        """
        Called when we receive a MSG_KEX_DH_GEX_REPLY message.  Payload::
            string server host key
            integer f (server DH public key)

        We verify the host key by calling verifyHostKey, then continue in
        _continueGEX_REPLY.
        """
        pubKey, packet = getNS(packet)
        f, packet = getMP(packet)
        signature, packet = getNS(packet)
        fingerprint = ':'.join(map(lambda c: '%02x'%ord(c),
            md5(pubKey).digest()))
        d = self.verifyHostKey(pubKey, fingerprint)
        d.addCallback(self._continueGEX_REPLY, pubKey, f, signature)
        d.addErrback(
            lambda unused: self.sendDisconnect(
                DISCONNECT_HOST_KEY_NOT_VERIFIABLE, 'bad host key'))
        return d


    def _continueGEX_REPLY(self, ignored, pubKey, f, signature):
        """
        The host key has been verified, so we generate the keys.

        @param pubKey: the public key blob for the server's public key.
        @type pubKey: C{str}
        @param f: the server's Diffie-Hellman public key.
        @type f: C{long}
        @param signature: the server's signature, verifying that it has the
            correct private key.
        @type signature: C{str}
        """
        serverKey = keys.Key.fromString(pubKey)
        sharedSecret = _MPpow(f, self.x, self.p)
        h = _kex.getHashProcessor(self.kexAlg)()
        h.update(NS(self.ourVersionString))
        h.update(NS(self.otherVersionString))
        h.update(NS(self.ourKexInitPayload))
        h.update(NS(self.otherKexInitPayload))
        h.update(NS(pubKey))
        h.update(struct.pack(
            '!LLL',
            self._dhMinimalGroupSize,
            self._dhPreferredGroupSize,
            self._dhMaximalGroupSize,
            ))
        h.update(MP(self.p))
        h.update(MP(self.g))
        h.update(self.e)
        h.update(MP(f))
        h.update(sharedSecret)
        exchangeHash = h.digest()
        if not serverKey.verify(signature, exchangeHash):
            self.sendDisconnect(DISCONNECT_KEY_EXCHANGE_FAILED,
                                'bad signature')
            return
        self._keySetup(sharedSecret, exchangeHash)


    def _keySetup(self, sharedSecret, exchangeHash):
        """
        See SSHTransportBase._keySetup().
        """
        SSHTransportBase._keySetup(self, sharedSecret, exchangeHash)
        if self._gotNewKeys:
            self.ssh_NEWKEYS('')


    def ssh_NEWKEYS(self, packet):
        """
        Called when we receive a MSG_NEWKEYS message.  No payload.
        If we've finished setting up our own keys, start using them.
        Otherwise, remember that we've received this message.
        """
        if packet != '':
            self.sendDisconnect(DISCONNECT_PROTOCOL_ERROR,
                                "NEWKEYS takes no data")
            return
        if not self.nextEncryptions.encBlockSize:
            self._gotNewKeys = 1
            return
        self._newKeys()
        self.connectionSecure()


    def ssh_SERVICE_ACCEPT(self, packet):
        """
        Called when we receive a MSG_SERVICE_ACCEPT message.  Payload::
            string service name

        Start the service we requested.
        """
        if packet == '':
            log.msg('got SERVICE_ACCEPT without payload')
        else:
            name = getNS(packet)[0]
            if name != self.instance.name:
                self.sendDisconnect(
                    DISCONNECT_PROTOCOL_ERROR,
                    "received accept for service we did not request")
        self.setService(self.instance)


    def requestService(self, instance):
        """
        Request that a service be run over this transport.

        @type instance: subclass of L{twisted.conch.ssh.service.SSHService}
        """
        self.sendPacket(MSG_SERVICE_REQUEST, NS(instance.name))
        self.instance = instance


    # client methods
    def verifyHostKey(self, hostKey, fingerprint):
        """
        Returns a Deferred that gets a callback if it is a valid key, or
        an errback if not.

        @type hostKey:      C{str}
        @type fingerprint:  C{str}
        @rtype:             L{twisted.internet.defer.Deferred}
        """
        # return if it's good
        return defer.fail(NotImplementedError())


    def connectionSecure(self):
        """
        Called when the encryption has been set up.  Generally,
        requestService() is called to run another service over the transport.
        """
        raise NotImplementedError()



class _DummyCipher:
    """
    A cipher for the none encryption method.

    @ivar block_size: the block size of the encryption.  In the case of the
    none cipher, this is 8 bytes.
    """
    block_size = 8


    def encrypt(self, x):
        return x


    decrypt = encrypt


class SSHCiphers:
    """
    SSHCiphers represents all the encryption operations that need to occur
    to encrypt and authenticate the SSH connection.

    @cvar cipherMap: A dictionary mapping SSH encryption names to 3-tuples of
                     (<Crypto.Cipher.* name>, <block size>, <is counter mode>)
    @cvar macMap: A dictionary mapping SSH MAC names to hash modules.

    @ivar outCipType: the string type of the outgoing cipher.
    @ivar inCipType: the string type of the incoming cipher.
    @ivar outMACType: the string type of the incoming MAC.
    @ivar inMACType: the string type of the incoming MAC.
    @ivar encBlockSize: the block size of the outgoing cipher.
    @ivar decBlockSize: the block size of the incoming cipher.
    @ivar verifyDigestSize: the size of the incoming MAC.
    @ivar outMAC: a tuple of (<hash module>, <inner key>, <outer key>,
        <digest size>) representing the outgoing MAC.
    @ivar inMAc: see outMAC, but for the incoming MAC.
    """

    cipherMap = {
        '3des-cbc': ('DES3', 24, False),
        'blowfish-cbc': ('Blowfish', 16, False),
        'aes256-cbc': ('AES', 32, False),
        'aes192-cbc': ('AES', 24, False),
        'aes128-cbc': ('AES', 16, False),
        'cast128-cbc': ('CAST', 16, False),
        'aes128-ctr': ('AES', 16, True),
        'aes192-ctr': ('AES', 24, True),
        'aes256-ctr': ('AES', 32, True),
        '3des-ctr': ('DES3', 24, True),
        'blowfish-ctr': ('Blowfish', 16, True),
        'cast128-ctr': ('CAST', 16, True),
        'none': (None, 0, False),
    }
    macMap = {
        'hmac-sha2-512': sha512,
        'hmac-sha2-256': sha256,
        'hmac-sha1': sha1,
        'hmac-md5': md5,
        'none': None
     }


    def __init__(self, outCip, inCip, outMac, inMac):
        self.outCipType = outCip
        self.inCipType = inCip
        self.outMACType = outMac
        self.inMACType = inMac
        self.encBlockSize = 0
        self.decBlockSize = 0
        self.verifyDigestSize = 0
        self.outMAC = (None, '', '', 0)
        self.inMAC = (None, '', '', 0)


    def setKeys(self, outIV, outKey, inIV, inKey, outInteg, inInteg):
        """
        Set up the ciphers and hashes using the given keys,

        @param outIV: the outgoing initialization vector
        @param outKey: the outgoing encryption key
        @param inIV: the incoming initialization vector
        @param inKey: the incoming encryption key
        @param outInteg: the outgoing integrity key
        @param inInteg: the incoming integrity key.
        """
        o = self._getCipher(self.outCipType, outIV, outKey)
        self.encrypt = o.encrypt
        self.encBlockSize = o.block_size
        o = self._getCipher(self.inCipType, inIV, inKey)
        self.decrypt = o.decrypt
        self.decBlockSize = o.block_size
        self.outMAC = self._getMAC(self.outMACType, outInteg)
        self.inMAC = self._getMAC(self.inMACType, inInteg)
        if self.inMAC:
            self.verifyDigestSize = self.inMAC[3]


    def _getCipher(self, cip, iv, key):
        """
        Creates an initialized cipher object.

        @param cip: the name of the cipher: maps into Crypto.Cipher.*
        @param iv: the initialzation vector
        @param key: the encryption key
        """
        modName, keySize, counterMode = self.cipherMap[cip]
        if not modName: # no cipher
            return _DummyCipher()
        mod = __import__('Crypto.Cipher.%s'%modName, {}, {}, 'x')
        if counterMode:
            return mod.new(key[:keySize], mod.MODE_CTR, iv[:mod.block_size],
                           counter=_Counter(iv, mod.block_size))
        else:
            return mod.new(key[:keySize], mod.MODE_CBC, iv[:mod.block_size])


    def _getMAC(self, mac, key):
        """
        Gets a 4-tuple representing the message authentication code.
        (<hash module>, <inner hash value>, <outer hash value>,
        <digest size>)

        @param mac: a key mapping into macMap
        @type mac: C{str}
        @param key: the MAC key.
        @type key: C{str}
        """
        mod = self.macMap[mac]
        if not mod:
            return (None, '', '', 0)

        # With stdlib we can only get attributes fron an instantiated object.
        hashObject = mod()
        digestSize = hashObject.digest_size
        blockSize = hashObject.block_size

        # Truncation here appears to contravene RFC 2104, section 2.  However,
        # implementing the hashing behavior prescribed by the RFC breaks
        # interoperability with OpenSSH (at least version 5.5p1).
        key = key[:digestSize] + ('\x00' * (blockSize - digestSize))
        i = string.translate(key, hmac.trans_36)
        o = string.translate(key, hmac.trans_5C)
        result = _MACParams((mod, i, o, digestSize))
        result.key = key
        return result


    def encrypt(self, blocks):
        """
        Encrypt blocks.  Overridden by the encrypt method of a
        Crypto.Cipher.* object in setKeys().

        @type blocks: C{str}
        """
        raise NotImplementedError()


    def decrypt(self, blocks):
        """
        Decrypt blocks.  See encrypt().

        @type blocks: C{str}
        """
        raise NotImplementedError()


    def makeMAC(self, seqid, data):
        """
        Create a message authentication code (MAC) for the given packet using
        the outgoing MAC values.

        @param seqid: the sequence ID of the outgoing packet
        @type seqid: C{int}
        @param data: the data to create a MAC for
        @type data: C{str}
        @rtype: C{str}
        """
        if not self.outMAC[0]:
            return ''
        data = struct.pack('>L', seqid) + data
        return hmac.HMAC(self.outMAC.key, data, self.outMAC[0]).digest()


    def verify(self, seqid, data, mac):
        """
        Verify an incoming MAC using the incoming MAC values.  Return True
        if the MAC is valid.

        @param seqid: the sequence ID of the incoming packet
        @type seqid: C{int}
        @param data: the packet data to verify
        @type data: C{str}
        @param mac: the MAC sent with the packet
        @type mac: C{str}
        @rtype: C{bool}
        """
        if not self.inMAC[0]:
            return mac == ''
        data = struct.pack('>L', seqid) + data
        outer = hmac.HMAC(self.inMAC.key, data, self.inMAC[0]).digest()
        return mac == outer


class _Counter:
    """
    Stateful counter which returns results packed in a byte string
    """


    def __init__(self, initialVector, blockSize):
        """
        @type initialVector: C{str}
        @param initialVector: A byte string representing the initial counter
                              value.
        @type blockSize: C{int}
        @param blockSize: The length of the output buffer, as well as the
        number of bytes at the beginning of C{initialVector} to consider.
        """
        initialVector = initialVector[:blockSize]
        self.count = getMP('\xff\xff\xff\xff' + initialVector)[0]
        self.blockSize = blockSize
        self.count = Util.number.long_to_bytes(self.count - 1)
        self.count = '\x00' * (self.blockSize - len(self.count)) + self.count
        self.count = array.array('c', self.count)
        self.len = len(self.count) - 1


    def __call__(self):
        """
        Increment the counter and return the new value.
        """
        i = self.len
        while i > -1:
            self.count[i] = n = chr((ord(self.count[i]) + 1) % 256)
            if n == '\x00':
                i -= 1
            else:
                return self.count.tostring()

        self.count = array.array('c', '\x00' * self.blockSize)
        return self.count.tostring()



DH_GENERATOR, DH_PRIME = _kex.getDHGeneratorAndPrime(
    'diffie-hellman-group1-sha1')


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
for name, value in globals().items():
    # Avoid legacy messages which overlap with never ones
    if name.startswith('MSG_') and not name.startswith('MSG_KEXDH_'):
        messages[value] = name
# Check for regressions (#5352)
if 'MSG_KEXDH_INIT' in messages or 'MSG_KEXDH_REPLY' in messages:
    raise RuntimeError(
        "legacy SSH mnemonics should not end up in messages dict")
