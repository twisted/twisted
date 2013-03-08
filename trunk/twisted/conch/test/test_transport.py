# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for ssh/transport.py and the classes therein.
"""

try:
    import pyasn1
except ImportError:
    pyasn1 = None

try:
    import Crypto.Cipher.DES3
except ImportError:
    Crypto = None

if pyasn1 is not None and Crypto is not None:
    dependencySkip = None
    from twisted.conch.ssh import transport, keys, factory
    from twisted.conch.test import keydata
else:
    if pyasn1 is None:
        dependencySkip = "Cannot run without PyASN1"
    elif Crypto is None:
        dependencySkip = "can't run w/o PyCrypto"

    class transport: # fictional modules to make classes work
        class SSHTransportBase: pass
        class SSHServerTransport: pass
        class SSHClientTransport: pass
    class factory:
        class SSHFactory:
            pass

from twisted.trial import unittest
from twisted.internet import defer
from twisted.protocols import loopback
from twisted.python import randbytes
from twisted.python.reflect import qual, getClass
from twisted.python.hashlib import md5, sha1
from twisted.conch.ssh import address, service, common
from twisted.test import proto_helpers

from twisted.conch.error import ConchError

class MockTransportBase(transport.SSHTransportBase):
    """
    A base class for the client and server protocols.  Stores the messages
    it receieves instead of ignoring them.

    @ivar errors: a list of tuples: (reasonCode, description)
    @ivar unimplementeds: a list of integers: sequence number
    @ivar debugs: a list of tuples: (alwaysDisplay, message, lang)
    @ivar ignoreds: a list of strings: ignored data
    """

    def connectionMade(self):
        """
        Set up instance variables.
        """
        transport.SSHTransportBase.connectionMade(self)
        self.errors = []
        self.unimplementeds = []
        self.debugs = []
        self.ignoreds = []
        self.gotUnsupportedVersion = None


    def _unsupportedVersionReceived(self, remoteVersion):
        """
        Intercept unsupported version call.

        @type remoteVersion: C{str}
        """
        self.gotUnsupportedVersion = remoteVersion
        return transport.SSHTransportBase._unsupportedVersionReceived(
            self, remoteVersion)


    def receiveError(self, reasonCode, description):
        """
        Store any errors received.

        @type reasonCode: C{int}
        @type description: C{str}
        """
        self.errors.append((reasonCode, description))


    def receiveUnimplemented(self, seqnum):
        """
        Store any unimplemented packet messages.

        @type seqnum: C{int}
        """
        self.unimplementeds.append(seqnum)


    def receiveDebug(self, alwaysDisplay, message, lang):
        """
        Store any debug messages.

        @type alwaysDisplay: C{bool}
        @type message: C{str}
        @type lang: C{str}
        """
        self.debugs.append((alwaysDisplay, message, lang))


    def ssh_IGNORE(self, packet):
        """
        Store any ignored data.

        @type packet: C{str}
        """
        self.ignoreds.append(packet)


class MockCipher(object):
    """
    A mocked-up version of twisted.conch.ssh.transport.SSHCiphers.
    """
    outCipType = 'test'
    encBlockSize = 6
    inCipType = 'test'
    decBlockSize = 6
    inMACType = 'test'
    outMACType = 'test'
    verifyDigestSize = 1
    usedEncrypt = False
    usedDecrypt = False
    outMAC = (None, '', '', 1)
    inMAC = (None, '', '', 1)
    keys = ()


    def encrypt(self, x):
        """
        Called to encrypt the packet.  Simply record that encryption was used
        and return the data unchanged.
        """
        self.usedEncrypt = True
        if (len(x) % self.encBlockSize) != 0:
            raise RuntimeError("length %i modulo blocksize %i is not 0: %i" %
                    (len(x), self.encBlockSize, len(x) % self.encBlockSize))
        return x


    def decrypt(self, x):
        """
        Called to decrypt the packet.  Simply record that decryption was used
        and return the data unchanged.
        """
        self.usedDecrypt = True
        if (len(x) % self.encBlockSize) != 0:
            raise RuntimeError("length %i modulo blocksize %i is not 0: %i" %
                    (len(x), self.decBlockSize, len(x) % self.decBlockSize))
        return x


    def makeMAC(self, outgoingPacketSequence, payload):
        """
        Make a Message Authentication Code by sending the character value of
        the outgoing packet.
        """
        return chr(outgoingPacketSequence)


    def verify(self, incomingPacketSequence, packet, macData):
        """
        Verify the Message Authentication Code by checking that the packet
        sequence number is the same.
        """
        return chr(incomingPacketSequence) == macData


    def setKeys(self, ivOut, keyOut, ivIn, keyIn, macIn, macOut):
        """
        Record the keys.
        """
        self.keys = (ivOut, keyOut, ivIn, keyIn, macIn, macOut)



class MockCompression:
    """
    A mocked-up compression, based on the zlib interface.  Instead of
    compressing, it reverses the data and adds a 0x66 byte to the end.
    """


    def compress(self, payload):
        return payload[::-1] # reversed


    def decompress(self, payload):
        return payload[:-1][::-1]


    def flush(self, kind):
        return '\x66'



class MockService(service.SSHService):
    """
    A mocked-up service, based on twisted.conch.ssh.service.SSHService.

    @ivar started: True if this service has been started.
    @ivar stopped: True if this service has been stopped.
    """
    name = "MockService"
    started = False
    stopped = False
    protocolMessages = {0xff: "MSG_TEST", 71: "MSG_fiction"}


    def logPrefix(self):
        return "MockService"


    def serviceStarted(self):
        """
        Record that the service was started.
        """
        self.started = True


    def serviceStopped(self):
        """
        Record that the service was stopped.
        """
        self.stopped = True


    def ssh_TEST(self, packet):
        """
        A message that this service responds to.
        """
        self.transport.sendPacket(0xff, packet)


class MockFactory(factory.SSHFactory):
    """
    A mocked-up factory based on twisted.conch.ssh.factory.SSHFactory.
    """
    services = {
        'ssh-userauth': MockService}


    def getPublicKeys(self):
        """
        Return the public keys that authenticate this server.
        """
        return {
            'ssh-rsa': keys.Key.fromString(keydata.publicRSA_openssh),
            'ssh-dsa': keys.Key.fromString(keydata.publicDSA_openssh)}


    def getPrivateKeys(self):
        """
        Return the private keys that authenticate this server.
        """
        return {
            'ssh-rsa': keys.Key.fromString(keydata.privateRSA_openssh),
            'ssh-dsa': keys.Key.fromString(keydata.privateDSA_openssh)}


    def getPrimes(self):
        """
        Return the Diffie-Hellman primes that can be used for the
        diffie-hellman-group-exchange-sha1 key exchange.
        """
        return {
            1024: ((2, transport.DH_PRIME),),
            2048: ((3, transport.DH_PRIME),),
            4096: ((5, 7),)}



class MockOldFactoryPublicKeys(MockFactory):
    """
    The old SSHFactory returned mappings from key names to strings from
    getPublicKeys().  We return those here for testing.
    """


    def getPublicKeys(self):
        """
        We used to map key types to public key blobs as strings.
        """
        keys = MockFactory.getPublicKeys(self)
        for name, key in keys.items()[:]:
            keys[name] = key.blob()
        return keys



class MockOldFactoryPrivateKeys(MockFactory):
    """
    The old SSHFactory returned mappings from key names to PyCrypto key
    objects from getPrivateKeys().  We return those here for testing.
    """


    def getPrivateKeys(self):
        """
        We used to map key types to PyCrypto key objects.
        """
        keys = MockFactory.getPrivateKeys(self)
        for name, key  in keys.items()[:]:
            keys[name] = key.keyObject
        return keys


class TransportTestCase(unittest.TestCase):
    """
    Base class for transport test cases.
    """
    klass = None

    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

    if pyasn1 is None:
        skip = "Cannot run without PyASN1"


    def setUp(self):
        self.transport = proto_helpers.StringTransport()
        self.proto = self.klass()
        self.packets = []
        def secureRandom(len):
            """
            Return a consistent entropy value
            """
            return '\x99' * len
        self.oldSecureRandom = randbytes.secureRandom
        randbytes.secureRandom = secureRandom
        def stubSendPacket(messageType, payload):
            self.packets.append((messageType, payload))
        self.proto.makeConnection(self.transport)
        # we just let the kex packet go into the transport
        self.proto.sendPacket = stubSendPacket


    def finishKeyExchange(self, proto):
        """
        Deliver enough additional messages to C{proto} so that the key exchange
        which is started in L{SSHTransportBase.connectionMade} completes and
        non-key exchange messages can be sent and received.
        """
        proto.dataReceived("SSH-2.0-BogoClient-1.2i\r\n")
        proto.dispatchMessage(
            transport.MSG_KEXINIT, self._A_KEXINIT_MESSAGE)
        proto._keySetup("foo", "bar")
        # SSHTransportBase can't handle MSG_NEWKEYS, or it would be the right
        # thing to deliver next.  _newKeys won't work either, because
        # sendKexInit (probably) hasn't been called.  sendKexInit is
        # responsible for setting up certain state _newKeys relies on.  So,
        # just change the key exchange state to what it would be when key
        # exchange is finished.
        proto._keyExchangeState = proto._KEY_EXCHANGE_NONE


    def tearDown(self):
        randbytes.secureRandom = self.oldSecureRandom
        self.oldSecureRandom = None


    def simulateKeyExchange(self, sharedSecret, exchangeHash):
        """
        Finish a key exchange by calling C{_keySetup} with the given arguments.
        Also do extra whitebox stuff to satisfy that method's assumption that
        some kind of key exchange has actually taken place.
        """
        self.proto._keyExchangeState = self.proto._KEY_EXCHANGE_REQUESTED
        self.proto._blockedByKeyExchange = []
        self.proto._keySetup(sharedSecret, exchangeHash)



class BaseSSHTransportTestCase(TransportTestCase):
    """
    Test TransportBase.  It implements the non-server/client specific
    parts of the SSH transport protocol.
    """

    klass = MockTransportBase

    _A_KEXINIT_MESSAGE = (
        "\xAA" * 16 +
        common.NS('diffie-hellman-group1-sha1') +
        common.NS('ssh-rsa') +
        common.NS('aes256-ctr') +
        common.NS('aes256-ctr') +
        common.NS('hmac-sha1') +
        common.NS('hmac-sha1') +
        common.NS('none') +
        common.NS('none') +
        common.NS('') +
        common.NS('') +
        '\x00' + '\x00\x00\x00\x00')

    def test_sendVersion(self):
        """
        Test that the first thing sent over the connection is the version
        string.
        """
        # the other setup was done in the setup method
        self.assertEqual(self.transport.value().split('\r\n', 1)[0],
                          "SSH-2.0-Twisted")


    def test_sendPacketPlain(self):
        """
        Test that plain (unencrypted, uncompressed) packets are sent
        correctly.  The format is::
            uint32 length (including type and padding length)
            byte padding length
            byte type
            bytes[length-padding length-2] data
            bytes[padding length] padding
        """
        proto = MockTransportBase()
        proto.makeConnection(self.transport)
        self.finishKeyExchange(proto)
        self.transport.clear()
        message = ord('A')
        payload = 'BCDEFG'
        proto.sendPacket(message, payload)
        value = self.transport.value()
        self.assertEqual(value, '\x00\x00\x00\x0c\x04ABCDEFG\x99\x99\x99\x99')


    def test_sendPacketEncrypted(self):
        """
        Test that packets sent while encryption is enabled are sent
        correctly.  The whole packet should be encrypted.
        """
        proto = MockTransportBase()
        proto.makeConnection(self.transport)
        self.finishKeyExchange(proto)
        proto.currentEncryptions = testCipher = MockCipher()
        message = ord('A')
        payload = 'BC'
        self.transport.clear()
        proto.sendPacket(message, payload)
        self.assertTrue(testCipher.usedEncrypt)
        value = self.transport.value()
        self.assertEqual(
            value,
            # Four byte length prefix
            '\x00\x00\x00\x08'
            # One byte padding length
            '\x04'
            # The actual application data
            'ABC'
            # "Random" padding - see the secureRandom monkeypatch in setUp
            '\x99\x99\x99\x99'
            # The MAC
            '\x02')


    def test_sendPacketCompressed(self):
        """
        Test that packets sent while compression is enabled are sent
        correctly.  The packet type and data should be encrypted.
        """
        proto = MockTransportBase()
        proto.makeConnection(self.transport)
        self.finishKeyExchange(proto)
        proto.outgoingCompression = MockCompression()
        self.transport.clear()
        proto.sendPacket(ord('A'), 'B')
        value = self.transport.value()
        self.assertEqual(
            value,
            '\x00\x00\x00\x0c\x08BA\x66\x99\x99\x99\x99\x99\x99\x99\x99')


    def test_sendPacketBoth(self):
        """
        Test that packets sent while compression and encryption are
        enabled are sent correctly.  The packet type and data should be
        compressed and then the whole packet should be encrypted.
        """
        proto = MockTransportBase()
        proto.makeConnection(self.transport)
        self.finishKeyExchange(proto)
        proto.currentEncryptions = testCipher = MockCipher()
        proto.outgoingCompression = MockCompression()
        message = ord('A')
        payload = 'BC'
        self.transport.clear()
        proto.sendPacket(message, payload)
        self.assertTrue(testCipher.usedEncrypt)
        value = self.transport.value()
        self.assertEqual(
            value,
            # Four byte length prefix
            '\x00\x00\x00\x0e'
            # One byte padding length
            '\x09'
            # Compressed application data
            'CBA\x66'
            # "Random" padding - see the secureRandom monkeypatch in setUp
            '\x99\x99\x99\x99\x99\x99\x99\x99\x99'
            # The MAC
            '\x02')


    def test_getPacketPlain(self):
        """
        Test that packets are retrieved correctly out of the buffer when
        no encryption is enabled.
        """
        proto = MockTransportBase()
        proto.makeConnection(self.transport)
        self.finishKeyExchange(proto)
        self.transport.clear()
        proto.sendPacket(ord('A'), 'BC')
        proto.buf = self.transport.value() + 'extra'
        self.assertEqual(proto.getPacket(), 'ABC')
        self.assertEqual(proto.buf, 'extra')


    def test_getPacketEncrypted(self):
        """
        Test that encrypted packets are retrieved correctly.
        See test_sendPacketEncrypted.
        """
        proto = MockTransportBase()
        proto.sendKexInit = lambda: None # don't send packets
        proto.makeConnection(self.transport)
        self.transport.clear()
        proto.currentEncryptions = testCipher = MockCipher()
        proto.sendPacket(ord('A'), 'BCD')
        value = self.transport.value()
        proto.buf = value[:MockCipher.decBlockSize]
        self.assertEqual(proto.getPacket(), None)
        self.assertTrue(testCipher.usedDecrypt)
        self.assertEqual(proto.first, '\x00\x00\x00\x0e\x09A')
        proto.buf += value[MockCipher.decBlockSize:]
        self.assertEqual(proto.getPacket(), 'ABCD')
        self.assertEqual(proto.buf, '')


    def test_getPacketCompressed(self):
        """
        Test that compressed packets are retrieved correctly.  See
        test_sendPacketCompressed.
        """
        proto = MockTransportBase()
        proto.makeConnection(self.transport)
        self.finishKeyExchange(proto)
        self.transport.clear()
        proto.outgoingCompression = MockCompression()
        proto.incomingCompression = proto.outgoingCompression
        proto.sendPacket(ord('A'), 'BCD')
        proto.buf = self.transport.value()
        self.assertEqual(proto.getPacket(), 'ABCD')


    def test_getPacketBoth(self):
        """
        Test that compressed and encrypted packets are retrieved correctly.
        See test_sendPacketBoth.
        """
        proto = MockTransportBase()
        proto.sendKexInit = lambda: None
        proto.makeConnection(self.transport)
        self.transport.clear()
        proto.currentEncryptions = MockCipher()
        proto.outgoingCompression = MockCompression()
        proto.incomingCompression = proto.outgoingCompression
        proto.sendPacket(ord('A'), 'BCDEFG')
        proto.buf = self.transport.value()
        self.assertEqual(proto.getPacket(), 'ABCDEFG')


    def test_ciphersAreValid(self):
        """
        Test that all the supportedCiphers are valid.
        """
        ciphers = transport.SSHCiphers('A', 'B', 'C', 'D')
        iv = key = '\x00' * 16
        for cipName in self.proto.supportedCiphers:
            self.assertTrue(ciphers._getCipher(cipName, iv, key))


    def test_sendKexInit(self):
        """
        Test that the KEXINIT (key exchange initiation) message is sent
        correctly.  Payload::
            bytes[16] cookie
            string key exchange algorithms
            string public key algorithms
            string outgoing ciphers
            string incoming ciphers
            string outgoing MACs
            string incoming MACs
            string outgoing compressions
            string incoming compressions
            bool first packet follows
            uint32 0
        """
        value = self.transport.value().split('\r\n', 1)[1]
        self.proto.buf = value
        packet = self.proto.getPacket()
        self.assertEqual(packet[0], chr(transport.MSG_KEXINIT))
        self.assertEqual(packet[1:17], '\x99' * 16)
        (kex, pubkeys, ciphers1, ciphers2, macs1, macs2, compressions1,
         compressions2, languages1, languages2,
         buf) = common.getNS(packet[17:], 10)

        self.assertEqual(kex, ','.join(self.proto.supportedKeyExchanges))
        self.assertEqual(pubkeys, ','.join(self.proto.supportedPublicKeys))
        self.assertEqual(ciphers1, ','.join(self.proto.supportedCiphers))
        self.assertEqual(ciphers2, ','.join(self.proto.supportedCiphers))
        self.assertEqual(macs1, ','.join(self.proto.supportedMACs))
        self.assertEqual(macs2, ','.join(self.proto.supportedMACs))
        self.assertEqual(compressions1,
                          ','.join(self.proto.supportedCompressions))
        self.assertEqual(compressions2,
                          ','.join(self.proto.supportedCompressions))
        self.assertEqual(languages1, ','.join(self.proto.supportedLanguages))
        self.assertEqual(languages2, ','.join(self.proto.supportedLanguages))
        self.assertEqual(buf, '\x00' * 5)


    def test_receiveKEXINITReply(self):
        """
        Immediately after connecting, the transport expects a KEXINIT message
        and does not reply to it.
        """
        self.transport.clear()
        self.proto.dispatchMessage(
            transport.MSG_KEXINIT, self._A_KEXINIT_MESSAGE)
        self.assertEqual(self.packets, [])


    def test_sendKEXINITReply(self):
        """
        When a KEXINIT message is received which is not a reply to an earlier
        KEXINIT message which was sent, a KEXINIT reply is sent.
        """
        self.finishKeyExchange(self.proto)
        del self.packets[:]

        self.proto.dispatchMessage(
            transport.MSG_KEXINIT, self._A_KEXINIT_MESSAGE)
        self.assertEqual(len(self.packets), 1)
        self.assertEqual(self.packets[0][0], transport.MSG_KEXINIT)


    def test_sendKexInitTwiceFails(self):
        """
        A new key exchange cannot be started while a key exchange is already in
        progress.  If an attempt is made to send a I{KEXINIT} message using
        L{SSHTransportBase.sendKexInit} while a key exchange is in progress
        causes that method to raise a L{RuntimeError}.
        """
        self.assertRaises(RuntimeError, self.proto.sendKexInit)


    def test_sendKexInitBlocksOthers(self):
        """
        After L{SSHTransportBase.sendKexInit} has been called, messages types
        other than the following are queued and not sent until after I{NEWKEYS}
        is sent by L{SSHTransportBase._keySetup}.

        RFC 4253, section 7.1.
        """
        # sendKexInit is called by connectionMade, which is called in setUp.
        # So we're in the state already.
        disallowedMessageTypes = [
            transport.MSG_SERVICE_REQUEST,
            transport.MSG_KEXINIT,
            ]

        # Drop all the bytes sent by setUp, they're not relevant to this test.
        self.transport.clear()

        # Get rid of the sendPacket monkey patch, we are testing the behavior
        # of sendPacket.
        del self.proto.sendPacket

        for messageType in disallowedMessageTypes:
            self.proto.sendPacket(messageType, 'foo')
            self.assertEqual(self.transport.value(), "")

        self.finishKeyExchange(self.proto)
        # Make the bytes written to the transport cleartext so it's easier to
        # make an assertion about them.
        self.proto.nextEncryptions = MockCipher()

        # Pseudo-deliver the peer's NEWKEYS message, which should flush the
        # messages which were queued above.
        self.proto._newKeys()
        self.assertEqual(self.transport.value().count("foo"), 2)


    def test_sendDebug(self):
        """
        Test that debug messages are sent correctly.  Payload::
            bool always display
            string debug message
            string language
        """
        self.proto.sendDebug("test", True, 'en')
        self.assertEqual(
            self.packets,
            [(transport.MSG_DEBUG,
              "\x01\x00\x00\x00\x04test\x00\x00\x00\x02en")])


    def test_receiveDebug(self):
        """
        Test that debug messages are received correctly.  See test_sendDebug.
        """
        self.proto.dispatchMessage(
            transport.MSG_DEBUG,
            '\x01\x00\x00\x00\x04test\x00\x00\x00\x02en')
        self.assertEqual(self.proto.debugs, [(True, 'test', 'en')])


    def test_sendIgnore(self):
        """
        Test that ignored messages are sent correctly.  Payload::
            string ignored data
        """
        self.proto.sendIgnore("test")
        self.assertEqual(
            self.packets, [(transport.MSG_IGNORE,
                            '\x00\x00\x00\x04test')])


    def test_receiveIgnore(self):
        """
        Test that ignored messages are received correctly.  See
        test_sendIgnore.
        """
        self.proto.dispatchMessage(transport.MSG_IGNORE, 'test')
        self.assertEqual(self.proto.ignoreds, ['test'])


    def test_sendUnimplemented(self):
        """
        Test that unimplemented messages are sent correctly.  Payload::
            uint32 sequence number
        """
        self.proto.sendUnimplemented()
        self.assertEqual(
            self.packets, [(transport.MSG_UNIMPLEMENTED,
                            '\x00\x00\x00\x00')])


    def test_receiveUnimplemented(self):
        """
        Test that unimplemented messages are received correctly.  See
        test_sendUnimplemented.
        """
        self.proto.dispatchMessage(transport.MSG_UNIMPLEMENTED,
                                   '\x00\x00\x00\xff')
        self.assertEqual(self.proto.unimplementeds, [255])


    def test_sendDisconnect(self):
        """
        Test that disconnection messages are sent correctly.  Payload::
            uint32 reason code
            string reason description
            string language
        """
        disconnected = [False]
        def stubLoseConnection():
            disconnected[0] = True
        self.transport.loseConnection = stubLoseConnection
        self.proto.sendDisconnect(0xff, "test")
        self.assertEqual(
            self.packets,
            [(transport.MSG_DISCONNECT,
              "\x00\x00\x00\xff\x00\x00\x00\x04test\x00\x00\x00\x00")])
        self.assertTrue(disconnected[0])


    def test_receiveDisconnect(self):
        """
        Test that disconnection messages are received correctly.  See
        test_sendDisconnect.
        """
        disconnected = [False]
        def stubLoseConnection():
            disconnected[0] = True
        self.transport.loseConnection = stubLoseConnection
        self.proto.dispatchMessage(transport.MSG_DISCONNECT,
                                   '\x00\x00\x00\xff\x00\x00\x00\x04test')
        self.assertEqual(self.proto.errors, [(255, 'test')])
        self.assertTrue(disconnected[0])


    def test_dataReceived(self):
        """
        Test that dataReceived parses packets and dispatches them to
        ssh_* methods.
        """
        kexInit = [False]
        def stubKEXINIT(packet):
            kexInit[0] = True
        self.proto.ssh_KEXINIT = stubKEXINIT
        self.proto.dataReceived(self.transport.value())
        self.assertTrue(self.proto.gotVersion)
        self.assertEqual(self.proto.ourVersionString,
                          self.proto.otherVersionString)
        self.assertTrue(kexInit[0])


    def test_service(self):
        """
        Test that the transport can set the running service and dispatches
        packets to the service's packetReceived method.
        """
        service = MockService()
        self.proto.setService(service)
        self.assertEqual(self.proto.service, service)
        self.assertTrue(service.started)
        self.proto.dispatchMessage(0xff, "test")
        self.assertEqual(self.packets, [(0xff, "test")])

        service2 = MockService()
        self.proto.setService(service2)
        self.assertTrue(service2.started)
        self.assertTrue(service.stopped)

        self.proto.connectionLost(None)
        self.assertTrue(service2.stopped)


    def test_avatar(self):
        """
        Test that the transport notifies the avatar of disconnections.
        """
        disconnected = [False]
        def logout():
            disconnected[0] = True
        self.proto.logoutFunction = logout
        self.proto.avatar = True

        self.proto.connectionLost(None)
        self.assertTrue(disconnected[0])


    def test_isEncrypted(self):
        """
        Test that the transport accurately reflects its encrypted status.
        """
        self.assertFalse(self.proto.isEncrypted('in'))
        self.assertFalse(self.proto.isEncrypted('out'))
        self.assertFalse(self.proto.isEncrypted('both'))
        self.proto.currentEncryptions = MockCipher()
        self.assertTrue(self.proto.isEncrypted('in'))
        self.assertTrue(self.proto.isEncrypted('out'))
        self.assertTrue(self.proto.isEncrypted('both'))
        self.proto.currentEncryptions = transport.SSHCiphers('none', 'none',
                                                             'none', 'none')
        self.assertFalse(self.proto.isEncrypted('in'))
        self.assertFalse(self.proto.isEncrypted('out'))
        self.assertFalse(self.proto.isEncrypted('both'))

        self.assertRaises(TypeError, self.proto.isEncrypted, 'bad')


    def test_isVerified(self):
        """
        Test that the transport accurately reflects its verified status.
        """
        self.assertFalse(self.proto.isVerified('in'))
        self.assertFalse(self.proto.isVerified('out'))
        self.assertFalse(self.proto.isVerified('both'))
        self.proto.currentEncryptions = MockCipher()
        self.assertTrue(self.proto.isVerified('in'))
        self.assertTrue(self.proto.isVerified('out'))
        self.assertTrue(self.proto.isVerified('both'))
        self.proto.currentEncryptions = transport.SSHCiphers('none', 'none',
                                                             'none', 'none')
        self.assertFalse(self.proto.isVerified('in'))
        self.assertFalse(self.proto.isVerified('out'))
        self.assertFalse(self.proto.isVerified('both'))

        self.assertRaises(TypeError, self.proto.isVerified, 'bad')


    def test_loseConnection(self):
        """
        Test that loseConnection sends a disconnect message and closes the
        connection.
        """
        disconnected = [False]
        def stubLoseConnection():
            disconnected[0] = True
        self.transport.loseConnection = stubLoseConnection
        self.proto.loseConnection()
        self.assertEqual(self.packets[0][0], transport.MSG_DISCONNECT)
        self.assertEqual(self.packets[0][1][3],
                          chr(transport.DISCONNECT_CONNECTION_LOST))


    def test_badVersion(self):
        """
        Test that the transport disconnects when it receives a bad version.
        """
        def testBad(version):
            self.packets = []
            self.proto.gotVersion = False
            disconnected = [False]
            def stubLoseConnection():
                disconnected[0] = True
            self.transport.loseConnection = stubLoseConnection
            for c in version + '\r\n':
                self.proto.dataReceived(c)
            self.assertTrue(disconnected[0])
            self.assertEqual(self.packets[0][0], transport.MSG_DISCONNECT)
            self.assertEqual(
                self.packets[0][1][3],
                chr(transport.DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED))
        testBad('SSH-1.5-OpenSSH')
        testBad('SSH-3.0-Twisted')
        testBad('GET / HTTP/1.1')


    def test_dataBeforeVersion(self):
        """
        Test that the transport ignores data sent before the version string.
        """
        proto = MockTransportBase()
        proto.makeConnection(proto_helpers.StringTransport())
        data = ("""here's some stuff beforehand
here's some other stuff
""" + proto.ourVersionString + "\r\n")
        [proto.dataReceived(c) for c in data]
        self.assertTrue(proto.gotVersion)
        self.assertEqual(proto.otherVersionString, proto.ourVersionString)


    def test_compatabilityVersion(self):
        """
        Test that the transport treats the compatbility version (1.99)
        as equivalent to version 2.0.
        """
        proto = MockTransportBase()
        proto.makeConnection(proto_helpers.StringTransport())
        proto.dataReceived("SSH-1.99-OpenSSH\n")
        self.assertTrue(proto.gotVersion)
        self.assertEqual(proto.otherVersionString, "SSH-1.99-OpenSSH")


    def test_supportedVersionsAreAllowed(self):
        """
        If an unusual SSH version is received and is included in
        C{supportedVersions}, an unsupported version error is not emitted.
        """
        proto = MockTransportBase()
        proto.supportedVersions = ("9.99", )
        proto.makeConnection(proto_helpers.StringTransport())
        proto.dataReceived("SSH-9.99-OpenSSH\n")
        self.assertFalse(proto.gotUnsupportedVersion)


    def test_unsupportedVersionsCallUnsupportedVersionReceived(self):
        """
        If an unusual SSH version is received and is not included in
        C{supportedVersions}, an unsupported version error is emitted.
        """
        proto = MockTransportBase()
        proto.supportedVersions = ("2.0", )
        proto.makeConnection(proto_helpers.StringTransport())
        proto.dataReceived("SSH-9.99-OpenSSH\n")
        self.assertEqual("9.99", proto.gotUnsupportedVersion)


    def test_badPackets(self):
        """
        Test that the transport disconnects with an error when it receives
        bad packets.
        """
        def testBad(packet, error=transport.DISCONNECT_PROTOCOL_ERROR):
            self.packets = []
            self.proto.buf = packet
            self.assertEqual(self.proto.getPacket(), None)
            self.assertEqual(len(self.packets), 1)
            self.assertEqual(self.packets[0][0], transport.MSG_DISCONNECT)
            self.assertEqual(self.packets[0][1][3], chr(error))

        testBad('\xff' * 8) # big packet
        testBad('\x00\x00\x00\x05\x00BCDE') # length not modulo blocksize
        oldEncryptions = self.proto.currentEncryptions
        self.proto.currentEncryptions = MockCipher()
        testBad('\x00\x00\x00\x08\x06AB123456', # bad MAC
                transport.DISCONNECT_MAC_ERROR)
        self.proto.currentEncryptions.decrypt = lambda x: x[:-1]
        testBad('\x00\x00\x00\x08\x06BCDEFGHIJK') # bad decryption
        self.proto.currentEncryptions = oldEncryptions
        self.proto.incomingCompression = MockCompression()
        def stubDecompress(payload):
            raise Exception('bad compression')
        self.proto.incomingCompression.decompress = stubDecompress
        testBad('\x00\x00\x00\x04\x00BCDE', # bad decompression
                transport.DISCONNECT_COMPRESSION_ERROR)
        self.flushLoggedErrors()


    def test_unimplementedPackets(self):
        """
        Test that unimplemented packet types cause MSG_UNIMPLEMENTED packets
        to be sent.
        """
        seqnum = self.proto.incomingPacketSequence
        def checkUnimplemented(seqnum=seqnum):
            self.assertEqual(self.packets[0][0],
                              transport.MSG_UNIMPLEMENTED)
            self.assertEqual(self.packets[0][1][3], chr(seqnum))
            self.proto.packets = []
            seqnum += 1

        self.proto.dispatchMessage(40, '')
        checkUnimplemented()
        transport.messages[41] = 'MSG_fiction'
        self.proto.dispatchMessage(41, '')
        checkUnimplemented()
        self.proto.dispatchMessage(60, '')
        checkUnimplemented()
        self.proto.setService(MockService())
        self.proto.dispatchMessage(70, '')
        checkUnimplemented()
        self.proto.dispatchMessage(71, '')
        checkUnimplemented()


    def test_getKey(self):
        """
        Test that _getKey generates the correct keys.
        """
        self.proto.sessionID = 'EF'

        k1 = sha1('AB' + 'CD' + 'K' + self.proto.sessionID).digest()
        k2 = sha1('ABCD' + k1).digest()
        self.assertEqual(self.proto._getKey('K', 'AB', 'CD'), k1 + k2)


    def test_multipleClasses(self):
        """
        Test that multiple instances have distinct states.
        """
        proto = self.proto
        proto.dataReceived(self.transport.value())
        proto.currentEncryptions = MockCipher()
        proto.outgoingCompression = MockCompression()
        proto.incomingCompression = MockCompression()
        proto.setService(MockService())
        proto2 = MockTransportBase()
        proto2.makeConnection(proto_helpers.StringTransport())
        proto2.sendIgnore('')
        self.failIfEquals(proto.gotVersion, proto2.gotVersion)
        self.failIfEquals(proto.transport, proto2.transport)
        self.failIfEquals(proto.outgoingPacketSequence,
                          proto2.outgoingPacketSequence)
        self.failIfEquals(proto.incomingPacketSequence,
                          proto2.incomingPacketSequence)
        self.failIfEquals(proto.currentEncryptions,
                          proto2.currentEncryptions)
        self.failIfEquals(proto.service, proto2.service)



class ServerAndClientSSHTransportBaseCase:
    """
    Tests that need to be run on both the server and the client.
    """


    def checkDisconnected(self, kind=None):
        """
        Helper function to check if the transport disconnected.
        """
        if kind is None:
            kind = transport.DISCONNECT_PROTOCOL_ERROR
        self.assertEqual(self.packets[-1][0], transport.MSG_DISCONNECT)
        self.assertEqual(self.packets[-1][1][3], chr(kind))


    def connectModifiedProtocol(self, protoModification,
            kind=None):
        """
        Helper function to connect a modified protocol to the test protocol
        and test for disconnection.
        """
        if kind is None:
            kind = transport.DISCONNECT_KEY_EXCHANGE_FAILED
        proto2 = self.klass()
        protoModification(proto2)
        proto2.makeConnection(proto_helpers.StringTransport())
        self.proto.dataReceived(proto2.transport.value())
        if kind:
            self.checkDisconnected(kind)
        return proto2


    def test_disconnectIfCantMatchKex(self):
        """
        Test that the transport disconnects if it can't match the key
        exchange
        """
        def blankKeyExchanges(proto2):
            proto2.supportedKeyExchanges = []
        self.connectModifiedProtocol(blankKeyExchanges)


    def test_disconnectIfCantMatchKeyAlg(self):
        """
        Like test_disconnectIfCantMatchKex, but for the key algorithm.
        """
        def blankPublicKeys(proto2):
            proto2.supportedPublicKeys = []
        self.connectModifiedProtocol(blankPublicKeys)


    def test_disconnectIfCantMatchCompression(self):
        """
        Like test_disconnectIfCantMatchKex, but for the compression.
        """
        def blankCompressions(proto2):
            proto2.supportedCompressions = []
        self.connectModifiedProtocol(blankCompressions)


    def test_disconnectIfCantMatchCipher(self):
        """
        Like test_disconnectIfCantMatchKex, but for the encryption.
        """
        def blankCiphers(proto2):
            proto2.supportedCiphers = []
        self.connectModifiedProtocol(blankCiphers)


    def test_disconnectIfCantMatchMAC(self):
        """
        Like test_disconnectIfCantMatchKex, but for the MAC.
        """
        def blankMACs(proto2):
            proto2.supportedMACs = []
        self.connectModifiedProtocol(blankMACs)

    def test_getPeer(self):
        """
        Test that the transport's L{getPeer} method returns an
        L{SSHTransportAddress} with the L{IAddress} of the peer.
        """
        self.assertEqual(self.proto.getPeer(),
                         address.SSHTransportAddress(
                self.proto.transport.getPeer()))

    def test_getHost(self):
        """
        Test that the transport's L{getHost} method returns an
        L{SSHTransportAddress} with the L{IAddress} of the host.
        """
        self.assertEqual(self.proto.getHost(),
                         address.SSHTransportAddress(
                self.proto.transport.getHost()))



class ServerSSHTransportTestCase(ServerAndClientSSHTransportBaseCase,
        TransportTestCase):
    """
    Tests for the SSHServerTransport.
    """

    klass = transport.SSHServerTransport


    def setUp(self):
        TransportTestCase.setUp(self)
        self.proto.factory = MockFactory()
        self.proto.factory.startFactory()


    def tearDown(self):
        TransportTestCase.tearDown(self)
        self.proto.factory.stopFactory()
        del self.proto.factory


    def test_KEXINIT(self):
        """
        Test that receiving a KEXINIT packet sets up the correct values on the
        server.
        """
        self.proto.dataReceived( 'SSH-2.0-Twisted\r\n\x00\x00\x01\xd4\t\x14'
                '\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99'
                '\x99\x00\x00\x00=diffie-hellman-group1-sha1,diffie-hellman-g'
                'roup-exchange-sha1\x00\x00\x00\x0fssh-dss,ssh-rsa\x00\x00\x00'
                '\x85aes128-ctr,aes128-cbc,aes192-ctr,aes192-cbc,aes256-ctr,ae'
                's256-cbc,cast128-ctr,cast128-cbc,blowfish-ctr,blowfish-cbc,3d'
                'es-ctr,3des-cbc\x00\x00\x00\x85aes128-ctr,aes128-cbc,aes192-c'
                'tr,aes192-cbc,aes256-ctr,aes256-cbc,cast128-ctr,cast128-cbc,b'
                'lowfish-ctr,blowfish-cbc,3des-ctr,3des-cbc\x00\x00\x00\x12hma'
                'c-md5,hmac-sha1\x00\x00\x00\x12hmac-md5,hmac-sha1\x00\x00\x00'
                '\tnone,zlib\x00\x00\x00\tnone,zlib\x00\x00\x00\x00\x00\x00'
                '\x00\x00\x00\x00\x00\x00\x00\x99\x99\x99\x99\x99\x99\x99\x99'
                '\x99')
        self.assertEqual(self.proto.kexAlg,
                          'diffie-hellman-group1-sha1')
        self.assertEqual(self.proto.keyAlg,
                          'ssh-dss')
        self.assertEqual(self.proto.outgoingCompressionType,
                          'none')
        self.assertEqual(self.proto.incomingCompressionType,
                          'none')
        ne = self.proto.nextEncryptions
        self.assertEqual(ne.outCipType, 'aes128-ctr')
        self.assertEqual(ne.inCipType, 'aes128-ctr')
        self.assertEqual(ne.outMACType, 'hmac-md5')
        self.assertEqual(ne.inMACType, 'hmac-md5')


    def test_ignoreGuessPacketKex(self):
        """
        The client is allowed to send a guessed key exchange packet
        after it sends the KEXINIT packet.  However, if the key exchanges
        do not match, that guess packet must be ignored.  This tests that
        the packet is ignored in the case of the key exchange method not
        matching.
        """
        kexInitPacket = '\x00' * 16 + (
            ''.join([common.NS(x) for x in
                     [','.join(y) for y in
                      [self.proto.supportedKeyExchanges[::-1],
                       self.proto.supportedPublicKeys,
                       self.proto.supportedCiphers,
                       self.proto.supportedCiphers,
                       self.proto.supportedMACs,
                       self.proto.supportedMACs,
                       self.proto.supportedCompressions,
                       self.proto.supportedCompressions,
                       self.proto.supportedLanguages,
                       self.proto.supportedLanguages]]])) + (
            '\xff\x00\x00\x00\x00')
        self.proto.ssh_KEXINIT(kexInitPacket)
        self.assertTrue(self.proto.ignoreNextPacket)
        self.proto.ssh_DEBUG("\x01\x00\x00\x00\x04test\x00\x00\x00\x00")
        self.assertTrue(self.proto.ignoreNextPacket)


        self.proto.ssh_KEX_DH_GEX_REQUEST_OLD('\x00\x00\x08\x00')
        self.assertFalse(self.proto.ignoreNextPacket)
        self.assertEqual(self.packets, [])
        self.proto.ignoreNextPacket = True

        self.proto.ssh_KEX_DH_GEX_REQUEST('\x00\x00\x08\x00' * 3)
        self.assertFalse(self.proto.ignoreNextPacket)
        self.assertEqual(self.packets, [])


    def test_ignoreGuessPacketKey(self):
        """
        Like test_ignoreGuessPacketKex, but for an incorrectly guessed
        public key format.
        """
        kexInitPacket = '\x00' * 16 + (
            ''.join([common.NS(x) for x in
                     [','.join(y) for y in
                      [self.proto.supportedKeyExchanges,
                       self.proto.supportedPublicKeys[::-1],
                       self.proto.supportedCiphers,
                       self.proto.supportedCiphers,
                       self.proto.supportedMACs,
                       self.proto.supportedMACs,
                       self.proto.supportedCompressions,
                       self.proto.supportedCompressions,
                       self.proto.supportedLanguages,
                       self.proto.supportedLanguages]]])) + (
            '\xff\x00\x00\x00\x00')
        self.proto.ssh_KEXINIT(kexInitPacket)
        self.assertTrue(self.proto.ignoreNextPacket)
        self.proto.ssh_DEBUG("\x01\x00\x00\x00\x04test\x00\x00\x00\x00")
        self.assertTrue(self.proto.ignoreNextPacket)

        self.proto.ssh_KEX_DH_GEX_REQUEST_OLD('\x00\x00\x08\x00')
        self.assertFalse(self.proto.ignoreNextPacket)
        self.assertEqual(self.packets, [])
        self.proto.ignoreNextPacket = True

        self.proto.ssh_KEX_DH_GEX_REQUEST('\x00\x00\x08\x00' * 3)
        self.assertFalse(self.proto.ignoreNextPacket)
        self.assertEqual(self.packets, [])


    def test_KEXDH_INIT(self):
        """
        Test that the KEXDH_INIT packet causes the server to send a
        KEXDH_REPLY with the server's public key and a signature.
        """
        self.proto.supportedKeyExchanges = ['diffie-hellman-group1-sha1']
        self.proto.supportedPublicKeys = ['ssh-rsa']
        self.proto.dataReceived(self.transport.value())
        e = pow(transport.DH_GENERATOR, 5000,
                transport.DH_PRIME)

        self.proto.ssh_KEX_DH_GEX_REQUEST_OLD(common.MP(e))
        y = common.getMP('\x00\x00\x00\x40' + '\x99' * 64)[0]
        f = common._MPpow(transport.DH_GENERATOR, y, transport.DH_PRIME)
        sharedSecret = common._MPpow(e, y, transport.DH_PRIME)

        h = sha1()
        h.update(common.NS(self.proto.ourVersionString) * 2)
        h.update(common.NS(self.proto.ourKexInitPayload) * 2)
        h.update(common.NS(self.proto.factory.publicKeys['ssh-rsa'].blob()))
        h.update(common.MP(e))
        h.update(f)
        h.update(sharedSecret)
        exchangeHash = h.digest()

        signature = self.proto.factory.privateKeys['ssh-rsa'].sign(
                exchangeHash)

        self.assertEqual(
            self.packets,
            [(transport.MSG_KEXDH_REPLY,
              common.NS(self.proto.factory.publicKeys['ssh-rsa'].blob())
              + f + common.NS(signature)),
             (transport.MSG_NEWKEYS, '')])


    def test_KEX_DH_GEX_REQUEST_OLD(self):
        """
        Test that the KEX_DH_GEX_REQUEST_OLD message causes the server
        to reply with a KEX_DH_GEX_GROUP message with the correct
        Diffie-Hellman group.
        """
        self.proto.supportedKeyExchanges = [
                'diffie-hellman-group-exchange-sha1']
        self.proto.supportedPublicKeys = ['ssh-rsa']
        self.proto.dataReceived(self.transport.value())
        self.proto.ssh_KEX_DH_GEX_REQUEST_OLD('\x00\x00\x04\x00')
        self.assertEqual(
            self.packets,
            [(transport.MSG_KEX_DH_GEX_GROUP,
              common.MP(transport.DH_PRIME) + '\x00\x00\x00\x01\x02')])
        self.assertEqual(self.proto.g, 2)
        self.assertEqual(self.proto.p, transport.DH_PRIME)


    def test_KEX_DH_GEX_REQUEST_OLD_badKexAlg(self):
        """
        Test that if the server recieves a KEX_DH_GEX_REQUEST_OLD message
        and the key exchange algorithm is not 'diffie-hellman-group1-sha1' or
        'diffie-hellman-group-exchange-sha1', we raise a ConchError.
        """
        self.proto.kexAlg = None
        self.assertRaises(ConchError, self.proto.ssh_KEX_DH_GEX_REQUEST_OLD,
                None)


    def test_KEX_DH_GEX_REQUEST(self):
        """
        Test that the KEX_DH_GEX_REQUEST message causes the server to reply
        with a KEX_DH_GEX_GROUP message with the correct Diffie-Hellman
        group.
        """
        self.proto.supportedKeyExchanges = [
            'diffie-hellman-group-exchange-sha1']
        self.proto.supportedPublicKeys = ['ssh-rsa']
        self.proto.dataReceived(self.transport.value())
        self.proto.ssh_KEX_DH_GEX_REQUEST('\x00\x00\x04\x00\x00\x00\x08\x00' +
                                          '\x00\x00\x0c\x00')
        self.assertEqual(
            self.packets,
            [(transport.MSG_KEX_DH_GEX_GROUP,
              common.MP(transport.DH_PRIME) + '\x00\x00\x00\x01\x03')])
        self.assertEqual(self.proto.g, 3)
        self.assertEqual(self.proto.p, transport.DH_PRIME)


    def test_KEX_DH_GEX_INIT_after_REQUEST(self):
        """
        Test that the KEX_DH_GEX_INIT message after the client sends
        KEX_DH_GEX_REQUEST causes the server to send a KEX_DH_GEX_INIT message
        with a public key and signature.
        """
        self.test_KEX_DH_GEX_REQUEST()
        e = pow(self.proto.g, 3, self.proto.p)
        y = common.getMP('\x00\x00\x00\x80' + '\x99' * 128)[0]
        f = common._MPpow(self.proto.g, y, self.proto.p)
        sharedSecret = common._MPpow(e, y, self.proto.p)
        h = sha1()
        h.update(common.NS(self.proto.ourVersionString) * 2)
        h.update(common.NS(self.proto.ourKexInitPayload) * 2)
        h.update(common.NS(self.proto.factory.publicKeys['ssh-rsa'].blob()))
        h.update('\x00\x00\x04\x00\x00\x00\x08\x00\x00\x00\x0c\x00')
        h.update(common.MP(self.proto.p))
        h.update(common.MP(self.proto.g))
        h.update(common.MP(e))
        h.update(f)
        h.update(sharedSecret)
        exchangeHash = h.digest()
        self.proto.ssh_KEX_DH_GEX_INIT(common.MP(e))
        self.assertEqual(
            self.packets[1],
            (transport.MSG_KEX_DH_GEX_REPLY,
             common.NS(self.proto.factory.publicKeys['ssh-rsa'].blob()) +
             f + common.NS(self.proto.factory.privateKeys['ssh-rsa'].sign(
                        exchangeHash))))


    def test_KEX_DH_GEX_INIT_after_REQUEST_OLD(self):
        """
        Test that the KEX_DH_GEX_INIT message after the client sends
        KEX_DH_GEX_REQUEST_OLD causes the server to sent a KEX_DH_GEX_INIT
        message with a public key and signature.
        """
        self.test_KEX_DH_GEX_REQUEST_OLD()
        e = pow(self.proto.g, 3, self.proto.p)
        y = common.getMP('\x00\x00\x00\x80' + '\x99' * 128)[0]
        f = common._MPpow(self.proto.g, y, self.proto.p)
        sharedSecret = common._MPpow(e, y, self.proto.p)
        h = sha1()
        h.update(common.NS(self.proto.ourVersionString) * 2)
        h.update(common.NS(self.proto.ourKexInitPayload) * 2)
        h.update(common.NS(self.proto.factory.publicKeys['ssh-rsa'].blob()))
        h.update('\x00\x00\x04\x00')
        h.update(common.MP(self.proto.p))
        h.update(common.MP(self.proto.g))
        h.update(common.MP(e))
        h.update(f)
        h.update(sharedSecret)
        exchangeHash = h.digest()
        self.proto.ssh_KEX_DH_GEX_INIT(common.MP(e))
        self.assertEqual(
            self.packets[1:],
            [(transport.MSG_KEX_DH_GEX_REPLY,
              common.NS(self.proto.factory.publicKeys['ssh-rsa'].blob()) +
              f + common.NS(self.proto.factory.privateKeys['ssh-rsa'].sign(
                            exchangeHash))),
             (transport.MSG_NEWKEYS, '')])


    def test_keySetup(self):
        """
        Test that _keySetup sets up the next encryption keys.
        """
        self.proto.nextEncryptions = MockCipher()
        self.simulateKeyExchange('AB', 'CD')
        self.assertEqual(self.proto.sessionID, 'CD')
        self.simulateKeyExchange('AB', 'EF')
        self.assertEqual(self.proto.sessionID, 'CD')
        self.assertEqual(self.packets[-1], (transport.MSG_NEWKEYS, ''))
        newKeys = [self.proto._getKey(c, 'AB', 'EF') for c in 'ABCDEF']
        self.assertEqual(
            self.proto.nextEncryptions.keys,
            (newKeys[1], newKeys[3], newKeys[0], newKeys[2], newKeys[5],
             newKeys[4]))


    def test_NEWKEYS(self):
        """
        Test that NEWKEYS transitions the keys in nextEncryptions to
        currentEncryptions.
        """
        self.test_KEXINIT()

        self.proto.nextEncryptions = transport.SSHCiphers('none', 'none',
                                                          'none', 'none')
        self.proto.ssh_NEWKEYS('')
        self.assertIdentical(self.proto.currentEncryptions,
                             self.proto.nextEncryptions)
        self.assertIdentical(self.proto.outgoingCompression, None)
        self.assertIdentical(self.proto.incomingCompression, None)
        self.proto.outgoingCompressionType = 'zlib'
        self.simulateKeyExchange('AB', 'CD')
        self.proto.ssh_NEWKEYS('')
        self.failIfIdentical(self.proto.outgoingCompression, None)
        self.proto.incomingCompressionType = 'zlib'
        self.simulateKeyExchange('AB', 'EF')
        self.proto.ssh_NEWKEYS('')
        self.failIfIdentical(self.proto.incomingCompression, None)


    def test_SERVICE_REQUEST(self):
        """
        Test that the SERVICE_REQUEST message requests and starts a
        service.
        """
        self.proto.ssh_SERVICE_REQUEST(common.NS('ssh-userauth'))
        self.assertEqual(self.packets, [(transport.MSG_SERVICE_ACCEPT,
                                          common.NS('ssh-userauth'))])
        self.assertEqual(self.proto.service.name, 'MockService')


    def test_disconnectNEWKEYSData(self):
        """
        Test that NEWKEYS disconnects if it receives data.
        """
        self.proto.ssh_NEWKEYS("bad packet")
        self.checkDisconnected()


    def test_disconnectSERVICE_REQUESTBadService(self):
        """
        Test that SERVICE_REQUESTS disconnects if an unknown service is
        requested.
        """
        self.proto.ssh_SERVICE_REQUEST(common.NS('no service'))
        self.checkDisconnected(transport.DISCONNECT_SERVICE_NOT_AVAILABLE)



class ClientSSHTransportTestCase(ServerAndClientSSHTransportBaseCase,
        TransportTestCase):
    """
    Tests for SSHClientTransport.
    """

    klass = transport.SSHClientTransport


    def test_KEXINIT(self):
        """
        Test that receiving a KEXINIT packet sets up the correct values on the
        client.  The way algorithms are picks is that the first item in the
        client's list that is also in the server's list is chosen.
        """
        self.proto.dataReceived( 'SSH-2.0-Twisted\r\n\x00\x00\x01\xd4\t\x14'
                '\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99\x99'
                '\x99\x00\x00\x00=diffie-hellman-group1-sha1,diffie-hellman-g'
                'roup-exchange-sha1\x00\x00\x00\x0fssh-dss,ssh-rsa\x00\x00\x00'
                '\x85aes128-ctr,aes128-cbc,aes192-ctr,aes192-cbc,aes256-ctr,ae'
                's256-cbc,cast128-ctr,cast128-cbc,blowfish-ctr,blowfish-cbc,3d'
                'es-ctr,3des-cbc\x00\x00\x00\x85aes128-ctr,aes128-cbc,aes192-c'
                'tr,aes192-cbc,aes256-ctr,aes256-cbc,cast128-ctr,cast128-cbc,b'
                'lowfish-ctr,blowfish-cbc,3des-ctr,3des-cbc\x00\x00\x00\x12hma'
                'c-md5,hmac-sha1\x00\x00\x00\x12hmac-md5,hmac-sha1\x00\x00\x00'
                '\tzlib,none\x00\x00\x00\tzlib,none\x00\x00\x00\x00\x00\x00'
                '\x00\x00\x00\x00\x00\x00\x00\x99\x99\x99\x99\x99\x99\x99\x99'
                '\x99')
        self.assertEqual(self.proto.kexAlg,
                          'diffie-hellman-group-exchange-sha1')
        self.assertEqual(self.proto.keyAlg,
                          'ssh-rsa')
        self.assertEqual(self.proto.outgoingCompressionType,
                          'none')
        self.assertEqual(self.proto.incomingCompressionType,
                          'none')
        ne = self.proto.nextEncryptions
        self.assertEqual(ne.outCipType, 'aes256-ctr')
        self.assertEqual(ne.inCipType, 'aes256-ctr')
        self.assertEqual(ne.outMACType, 'hmac-sha1')
        self.assertEqual(ne.inMACType, 'hmac-sha1')


    def verifyHostKey(self, pubKey, fingerprint):
        """
        Mock version of SSHClientTransport.verifyHostKey.
        """
        self.calledVerifyHostKey = True
        self.assertEqual(pubKey, self.blob)
        self.assertEqual(fingerprint.replace(':', ''),
                          md5(pubKey).hexdigest())
        return defer.succeed(True)


    def setUp(self):
        TransportTestCase.setUp(self)
        self.blob = keys.Key.fromString(keydata.publicRSA_openssh).blob()
        self.privObj = keys.Key.fromString(keydata.privateRSA_openssh)
        self.calledVerifyHostKey = False
        self.proto.verifyHostKey = self.verifyHostKey


    def test_notImplementedClientMethods(self):
        """
        verifyHostKey() should return a Deferred which fails with a
        NotImplementedError exception.  connectionSecure() should raise
        NotImplementedError().
        """
        self.assertRaises(NotImplementedError, self.klass().connectionSecure)
        def _checkRaises(f):
            f.trap(NotImplementedError)
        d = self.klass().verifyHostKey(None, None)
        return d.addCallback(self.fail).addErrback(_checkRaises)


    def test_KEXINIT_groupexchange(self):
        """
        Test that a KEXINIT packet with a group-exchange key exchange results
        in a KEX_DH_GEX_REQUEST_OLD message..
        """
        self.proto.supportedKeyExchanges = [
            'diffie-hellman-group-exchange-sha1']
        self.proto.dataReceived(self.transport.value())
        self.assertEqual(self.packets, [(transport.MSG_KEX_DH_GEX_REQUEST_OLD,
                                          '\x00\x00\x08\x00')])


    def test_KEXINIT_group1(self):
        """
        Like test_KEXINIT_groupexchange, but for the group-1 key exchange.
        """
        self.proto.supportedKeyExchanges = ['diffie-hellman-group1-sha1']
        self.proto.dataReceived(self.transport.value())
        self.assertEqual(common.MP(self.proto.x)[5:], '\x99' * 64)
        self.assertEqual(self.packets,
                          [(transport.MSG_KEXDH_INIT, self.proto.e)])


    def test_KEXINIT_badKexAlg(self):
        """
        Test that the client raises a ConchError if it receives a
        KEXINIT message bug doesn't have a key exchange algorithm that we
        understand.
        """
        self.proto.supportedKeyExchanges = ['diffie-hellman-group2-sha1']
        data = self.transport.value().replace('group1', 'group2')
        self.assertRaises(ConchError, self.proto.dataReceived, data)


    def test_KEXDH_REPLY(self):
        """
        Test that the KEXDH_REPLY message verifies the server.
        """
        self.test_KEXINIT_group1()

        sharedSecret = common._MPpow(transport.DH_GENERATOR,
                                     self.proto.x, transport.DH_PRIME)
        h = sha1()
        h.update(common.NS(self.proto.ourVersionString) * 2)
        h.update(common.NS(self.proto.ourKexInitPayload) * 2)
        h.update(common.NS(self.blob))
        h.update(self.proto.e)
        h.update('\x00\x00\x00\x01\x02') # f
        h.update(sharedSecret)
        exchangeHash = h.digest()

        def _cbTestKEXDH_REPLY(value):
            self.assertIdentical(value, None)
            self.assertEqual(self.calledVerifyHostKey, True)
            self.assertEqual(self.proto.sessionID, exchangeHash)

        signature = self.privObj.sign(exchangeHash)

        d = self.proto.ssh_KEX_DH_GEX_GROUP(
            (common.NS(self.blob) + '\x00\x00\x00\x01\x02' +
             common.NS(signature)))
        d.addCallback(_cbTestKEXDH_REPLY)

        return d


    def test_KEX_DH_GEX_GROUP(self):
        """
        Test that the KEX_DH_GEX_GROUP message results in a
        KEX_DH_GEX_INIT message with the client's Diffie-Hellman public key.
        """
        self.test_KEXINIT_groupexchange()
        self.proto.ssh_KEX_DH_GEX_GROUP(
            '\x00\x00\x00\x01\x0f\x00\x00\x00\x01\x02')
        self.assertEqual(self.proto.p, 15)
        self.assertEqual(self.proto.g, 2)
        self.assertEqual(common.MP(self.proto.x)[5:], '\x99' * 40)
        self.assertEqual(self.proto.e,
                          common.MP(pow(2, self.proto.x, 15)))
        self.assertEqual(self.packets[1:], [(transport.MSG_KEX_DH_GEX_INIT,
                                              self.proto.e)])


    def test_KEX_DH_GEX_REPLY(self):
        """
        Test that the KEX_DH_GEX_REPLY message results in a verified
        server.
        """

        self.test_KEX_DH_GEX_GROUP()
        sharedSecret = common._MPpow(3, self.proto.x, self.proto.p)
        h = sha1()
        h.update(common.NS(self.proto.ourVersionString) * 2)
        h.update(common.NS(self.proto.ourKexInitPayload) * 2)
        h.update(common.NS(self.blob))
        h.update('\x00\x00\x08\x00\x00\x00\x00\x01\x0f\x00\x00\x00\x01\x02')
        h.update(self.proto.e)
        h.update('\x00\x00\x00\x01\x03') # f
        h.update(sharedSecret)
        exchangeHash = h.digest()

        def _cbTestKEX_DH_GEX_REPLY(value):
            self.assertIdentical(value, None)
            self.assertEqual(self.calledVerifyHostKey, True)
            self.assertEqual(self.proto.sessionID, exchangeHash)

        signature = self.privObj.sign(exchangeHash)

        d = self.proto.ssh_KEX_DH_GEX_REPLY(
            common.NS(self.blob) +
            '\x00\x00\x00\x01\x03' +
            common.NS(signature))
        d.addCallback(_cbTestKEX_DH_GEX_REPLY)
        return d


    def test_keySetup(self):
        """
        Test that _keySetup sets up the next encryption keys.
        """
        self.proto.nextEncryptions = MockCipher()
        self.simulateKeyExchange('AB', 'CD')
        self.assertEqual(self.proto.sessionID, 'CD')
        self.simulateKeyExchange('AB', 'EF')
        self.assertEqual(self.proto.sessionID, 'CD')
        self.assertEqual(self.packets[-1], (transport.MSG_NEWKEYS, ''))
        newKeys = [self.proto._getKey(c, 'AB', 'EF') for c in 'ABCDEF']
        self.assertEqual(self.proto.nextEncryptions.keys,
                          (newKeys[0], newKeys[2], newKeys[1], newKeys[3],
                           newKeys[4], newKeys[5]))


    def test_NEWKEYS(self):
        """
        Test that NEWKEYS transitions the keys from nextEncryptions to
        currentEncryptions.
        """
        self.test_KEXINIT()
        secure = [False]
        def stubConnectionSecure():
            secure[0] = True
        self.proto.connectionSecure = stubConnectionSecure

        self.proto.nextEncryptions = transport.SSHCiphers(
            'none', 'none', 'none', 'none')
        self.simulateKeyExchange('AB', 'CD')
        self.assertNotIdentical(
            self.proto.currentEncryptions, self.proto.nextEncryptions)

        self.proto.nextEncryptions = MockCipher()
        self.proto.ssh_NEWKEYS('')
        self.assertIdentical(self.proto.outgoingCompression, None)
        self.assertIdentical(self.proto.incomingCompression, None)
        self.assertIdentical(self.proto.currentEncryptions,
                             self.proto.nextEncryptions)
        self.assertTrue(secure[0])
        self.proto.outgoingCompressionType = 'zlib'
        self.simulateKeyExchange('AB', 'GH')
        self.proto.ssh_NEWKEYS('')
        self.failIfIdentical(self.proto.outgoingCompression, None)
        self.proto.incomingCompressionType = 'zlib'
        self.simulateKeyExchange('AB', 'IJ')
        self.proto.ssh_NEWKEYS('')
        self.failIfIdentical(self.proto.incomingCompression, None)


    def test_SERVICE_ACCEPT(self):
        """
        Test that the SERVICE_ACCEPT packet starts the requested service.
        """
        self.proto.instance = MockService()
        self.proto.ssh_SERVICE_ACCEPT('\x00\x00\x00\x0bMockService')
        self.assertTrue(self.proto.instance.started)


    def test_requestService(self):
        """
        Test that requesting a service sends a SERVICE_REQUEST packet.
        """
        self.proto.requestService(MockService())
        self.assertEqual(self.packets, [(transport.MSG_SERVICE_REQUEST,
                                          '\x00\x00\x00\x0bMockService')])


    def test_disconnectKEXDH_REPLYBadSignature(self):
        """
        Test that KEXDH_REPLY disconnects if the signature is bad.
        """
        self.test_KEXDH_REPLY()
        self.proto._continueKEXDH_REPLY(None, self.blob, 3, "bad signature")
        self.checkDisconnected(transport.DISCONNECT_KEY_EXCHANGE_FAILED)


    def test_disconnectGEX_REPLYBadSignature(self):
        """
        Like test_disconnectKEXDH_REPLYBadSignature, but for DH_GEX_REPLY.
        """
        self.test_KEX_DH_GEX_REPLY()
        self.proto._continueGEX_REPLY(None, self.blob, 3, "bad signature")
        self.checkDisconnected(transport.DISCONNECT_KEY_EXCHANGE_FAILED)


    def test_disconnectNEWKEYSData(self):
        """
        Test that NEWKEYS disconnects if it receives data.
        """
        self.proto.ssh_NEWKEYS("bad packet")
        self.checkDisconnected()


    def test_disconnectSERVICE_ACCEPT(self):
        """
        Test that SERVICE_ACCEPT disconnects if the accepted protocol is
        differet from the asked-for protocol.
        """
        self.proto.instance = MockService()
        self.proto.ssh_SERVICE_ACCEPT('\x00\x00\x00\x03bad')
        self.checkDisconnected()


    def test_noPayloadSERVICE_ACCEPT(self):
        """
        Some commercial SSH servers don't send a payload with the
        SERVICE_ACCEPT message.  Conch pretends that it got the correct
        name of the service.
        """
        self.proto.instance = MockService()
        self.proto.ssh_SERVICE_ACCEPT('') # no payload
        self.assertTrue(self.proto.instance.started)
        self.assertEquals(len(self.packets), 0) # not disconnected



class SSHCiphersTestCase(unittest.TestCase):
    """
    Tests for the SSHCiphers helper class.
    """
    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

    if pyasn1 is None:
        skip = "Cannot run without PyASN1"


    def test_init(self):
        """
        Test that the initializer sets up the SSHCiphers object.
        """
        ciphers = transport.SSHCiphers('A', 'B', 'C', 'D')
        self.assertEqual(ciphers.outCipType, 'A')
        self.assertEqual(ciphers.inCipType, 'B')
        self.assertEqual(ciphers.outMACType, 'C')
        self.assertEqual(ciphers.inMACType, 'D')


    def test_getCipher(self):
        """
        Test that the _getCipher method returns the correct cipher.
        """
        ciphers = transport.SSHCiphers('A', 'B', 'C', 'D')
        iv = key = '\x00' * 16
        for cipName, (modName, keySize, counter) in ciphers.cipherMap.items():
            cip = ciphers._getCipher(cipName, iv, key)
            if cipName == 'none':
                self.assertIsInstance(cip, transport._DummyCipher)
            else:
                self.assertTrue(getClass(cip).__name__.startswith(modName))


    def test_getMAC(self):
        """
        Test that the _getMAC method returns the correct MAC.
        """
        ciphers = transport.SSHCiphers('A', 'B', 'C', 'D')
        key = '\x00' * 64
        for macName, mac in ciphers.macMap.items():
            mod = ciphers._getMAC(macName, key)
            if macName == 'none':
                self.assertIdentical(mac, None)
            else:
                self.assertEqual(mod[0], mac)
                self.assertEqual(mod[1],
                                  Crypto.Cipher.XOR.new('\x36').encrypt(key))
                self.assertEqual(mod[2],
                                  Crypto.Cipher.XOR.new('\x5c').encrypt(key))
                self.assertEqual(mod[3], len(mod[0]().digest()))


    def test_setKeysCiphers(self):
        """
        Test that setKeys sets up the ciphers.
        """
        key = '\x00' * 64
        cipherItems = transport.SSHCiphers.cipherMap.items()
        for cipName, (modName, keySize, counter) in cipherItems:
            encCipher = transport.SSHCiphers(cipName, 'none', 'none', 'none')
            decCipher = transport.SSHCiphers('none', cipName, 'none', 'none')
            cip = encCipher._getCipher(cipName, key, key)
            bs = cip.block_size
            encCipher.setKeys(key, key, '', '', '', '')
            decCipher.setKeys('', '', key, key, '', '')
            self.assertEqual(encCipher.encBlockSize, bs)
            self.assertEqual(decCipher.decBlockSize, bs)
            enc = cip.encrypt(key[:bs])
            enc2 = cip.encrypt(key[:bs])
            if counter:
                self.failIfEquals(enc, enc2)
            self.assertEqual(encCipher.encrypt(key[:bs]), enc)
            self.assertEqual(encCipher.encrypt(key[:bs]), enc2)
            self.assertEqual(decCipher.decrypt(enc), key[:bs])
            self.assertEqual(decCipher.decrypt(enc2), key[:bs])


    def test_setKeysMACs(self):
        """
        Test that setKeys sets up the MACs.
        """
        key = '\x00' * 64
        for macName, mod in transport.SSHCiphers.macMap.items():
            outMac = transport.SSHCiphers('none', 'none', macName, 'none')
            inMac = transport.SSHCiphers('none', 'none', 'none', macName)
            outMac.setKeys('', '', '', '', key, '')
            inMac.setKeys('', '', '', '', '', key)
            if mod:
                ds = mod().digest_size
            else:
                ds = 0
            self.assertEqual(inMac.verifyDigestSize, ds)
            if mod:
                mod, i, o, ds = outMac._getMAC(macName, key)
            seqid = 0
            data = key
            packet = '\x00' * 4 + key
            if mod:
                mac = mod(o + mod(i + packet).digest()).digest()
            else:
                mac = ''
            self.assertEqual(outMac.makeMAC(seqid, data), mac)
            self.assertTrue(inMac.verify(seqid, data, mac))



class CounterTestCase(unittest.TestCase):
    """
    Tests for the _Counter helper class.
    """
    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

    if pyasn1 is None:
        skip = "Cannot run without PyASN1"


    def test_init(self):
        """
        Test that the counter is initialized correctly.
        """
        counter = transport._Counter('\x00' * 8 + '\xff' * 8, 8)
        self.assertEqual(counter.blockSize, 8)
        self.assertEqual(counter.count.tostring(), '\x00' * 8)


    def test_count(self):
        """
        Test that the counter counts incrementally and wraps at the top.
        """
        counter = transport._Counter('\x00', 1)
        self.assertEqual(counter(), '\x01')
        self.assertEqual(counter(), '\x02')
        [counter() for i in range(252)]
        self.assertEqual(counter(), '\xff')
        self.assertEqual(counter(), '\x00')



class TransportLoopbackTestCase(unittest.TestCase):
    """
    Test the server transport and client transport against each other,
    """
    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

    if pyasn1 is None:
        skip = "Cannot run without PyASN1"


    def _runClientServer(self, mod):
        """
        Run an async client and server, modifying each using the mod function
        provided.  Returns a Deferred called back when both Protocols have
        disconnected.

        @type mod: C{func}
        @rtype: C{defer.Deferred}
        """
        factory = MockFactory()
        server = transport.SSHServerTransport()
        server.factory = factory
        factory.startFactory()
        server.errors = []
        server.receiveError = lambda code, desc: server.errors.append((
                code, desc))
        client = transport.SSHClientTransport()
        client.verifyHostKey = lambda x, y: defer.succeed(None)
        client.errors = []
        client.receiveError = lambda code, desc: client.errors.append((
                code, desc))
        client.connectionSecure = lambda: client.loseConnection()
        server = mod(server)
        client = mod(client)
        def check(ignored, server, client):
            name = repr([server.supportedCiphers[0],
                         server.supportedMACs[0],
                         server.supportedKeyExchanges[0],
                         server.supportedCompressions[0]])
            self.assertEqual(client.errors, [])
            self.assertEqual(server.errors, [(
                        transport.DISCONNECT_CONNECTION_LOST,
                        "user closed connection")])
            if server.supportedCiphers[0] == 'none':
                self.assertFalse(server.isEncrypted(), name)
                self.assertFalse(client.isEncrypted(), name)
            else:
                self.assertTrue(server.isEncrypted(), name)
                self.assertTrue(client.isEncrypted(), name)
            if server.supportedMACs[0] == 'none':
                self.assertFalse(server.isVerified(), name)
                self.assertFalse(client.isVerified(), name)
            else:
                self.assertTrue(server.isVerified(), name)
                self.assertTrue(client.isVerified(), name)

        d = loopback.loopbackAsync(server, client)
        d.addCallback(check, server, client)
        return d


    def test_ciphers(self):
        """
        Test that the client and server play nicely together, in all
        the various combinations of ciphers.
        """
        deferreds = []
        for cipher in transport.SSHTransportBase.supportedCiphers + ['none']:
            def setCipher(proto):
                proto.supportedCiphers = [cipher]
                return proto
            deferreds.append(self._runClientServer(setCipher))
        return defer.DeferredList(deferreds, fireOnOneErrback=True)


    def test_macs(self):
        """
        Like test_ciphers, but for the various MACs.
        """
        deferreds = []
        for mac in transport.SSHTransportBase.supportedMACs + ['none']:
            def setMAC(proto):
                proto.supportedMACs = [mac]
                return proto
            deferreds.append(self._runClientServer(setMAC))
        return defer.DeferredList(deferreds, fireOnOneErrback=True)


    def test_keyexchanges(self):
        """
        Like test_ciphers, but for the various key exchanges.
        """
        deferreds = []
        for kex in transport.SSHTransportBase.supportedKeyExchanges:
            def setKeyExchange(proto):
                proto.supportedKeyExchanges = [kex]
                return proto
            deferreds.append(self._runClientServer(setKeyExchange))
        return defer.DeferredList(deferreds, fireOnOneErrback=True)


    def test_compressions(self):
        """
        Like test_ciphers, but for the various compressions.
        """
        deferreds = []
        for compression in transport.SSHTransportBase.supportedCompressions:
            def setCompression(proto):
                proto.supportedCompressions = [compression]
                return proto
            deferreds.append(self._runClientServer(setCompression))
        return defer.DeferredList(deferreds, fireOnOneErrback=True)


class RandomNumberTestCase(unittest.TestCase):
    """
    Tests for the random number generator L{_getRandomNumber} and private
    key generator L{_generateX}.
    """
    skip = dependencySkip

    def test_usesSuppliedRandomFunction(self):
        """
        L{_getRandomNumber} returns an integer constructed directly from the
        bytes returned by the random byte generator passed to it.
        """
        def random(bytes):
            # The number of bytes requested will be the value of each byte
            # we return.
            return chr(bytes) * bytes
        self.assertEqual(
            transport._getRandomNumber(random, 32),
            4 << 24 | 4 << 16 | 4 << 8 | 4)


    def test_rejectsNonByteMultiples(self):
        """
        L{_getRandomNumber} raises L{ValueError} if the number of bits
        passed to L{_getRandomNumber} is not a multiple of 8.
        """
        self.assertRaises(
            ValueError,
            transport._getRandomNumber, None, 9)


    def test_excludesSmall(self):
        """
        If the random byte generator passed to L{_generateX} produces bytes
        which would result in 0 or 1 being returned, these bytes are
        discarded and another attempt is made to produce a larger value.
        """
        results = [chr(0), chr(1), chr(127)]
        def random(bytes):
            return results.pop(0) * bytes
        self.assertEqual(
            transport._generateX(random, 8),
            127)


    def test_excludesLarge(self):
        """
        If the random byte generator passed to L{_generateX} produces bytes
        which would result in C{(2 ** bits) - 1} being returned, these bytes
        are discarded and another attempt is made to produce a smaller
        value.
        """
        results = [chr(255), chr(64)]
        def random(bytes):
            return results.pop(0) * bytes
        self.assertEqual(
            transport._generateX(random, 8),
            64)



class OldFactoryTestCase(unittest.TestCase):
    """
    The old C{SSHFactory.getPublicKeys}() returned mappings of key names to
    strings of key blobs and mappings of key names to PyCrypto key objects from
    C{SSHFactory.getPrivateKeys}() (they could also be specified with the
    C{publicKeys} and C{privateKeys} attributes).  This is no longer supported
    by the C{SSHServerTransport}, so we warn the user if they create an old
    factory.
    """

    if Crypto is None:
        skip = "cannot run w/o PyCrypto"

    if pyasn1 is None:
        skip = "Cannot run without PyASN1"


    def test_getPublicKeysWarning(self):
        """
        If the return value of C{getPublicKeys}() isn't a mapping from key
        names to C{Key} objects, then warn the user and convert the mapping.
        """
        sshFactory = MockOldFactoryPublicKeys()
        self.assertWarns(DeprecationWarning,
                "Returning a mapping from strings to strings from"
                " getPublicKeys()/publicKeys (in %s) is deprecated.  Return "
                "a mapping from strings to Key objects instead." %
                (qual(MockOldFactoryPublicKeys),),
                factory.__file__, sshFactory.startFactory)
        self.assertEqual(sshFactory.publicKeys, MockFactory().getPublicKeys())


    def test_getPrivateKeysWarning(self):
        """
        If the return value of C{getPrivateKeys}() isn't a mapping from key
        names to C{Key} objects, then warn the user and convert the mapping.
        """
        sshFactory = MockOldFactoryPrivateKeys()
        self.assertWarns(DeprecationWarning,
                "Returning a mapping from strings to PyCrypto key objects from"
                " getPrivateKeys()/privateKeys (in %s) is deprecated.  Return"
                " a mapping from strings to Key objects instead." %
                (qual(MockOldFactoryPrivateKeys),),
                factory.__file__, sshFactory.startFactory)
        self.assertEqual(sshFactory.privateKeys,
                          MockFactory().getPrivateKeys())


    def test_publicKeysWarning(self):
        """
        If the value of the C{publicKeys} attribute isn't a mapping from key
        names to C{Key} objects, then warn the user and convert the mapping.
        """
        sshFactory = MockOldFactoryPublicKeys()
        sshFactory.publicKeys = sshFactory.getPublicKeys()
        self.assertWarns(DeprecationWarning,
                "Returning a mapping from strings to strings from"
                " getPublicKeys()/publicKeys (in %s) is deprecated.  Return "
                "a mapping from strings to Key objects instead." %
                (qual(MockOldFactoryPublicKeys),),
                factory.__file__, sshFactory.startFactory)
        self.assertEqual(sshFactory.publicKeys, MockFactory().getPublicKeys())


    def test_privateKeysWarning(self):
        """
        If the return value of C{privateKeys} attribute isn't a mapping from
        key names to C{Key} objects, then warn the user and convert the
        mapping.
        """
        sshFactory = MockOldFactoryPrivateKeys()
        sshFactory.privateKeys = sshFactory.getPrivateKeys()
        self.assertWarns(DeprecationWarning,
                "Returning a mapping from strings to PyCrypto key objects from"
                " getPrivateKeys()/privateKeys (in %s) is deprecated.  Return"
                " a mapping from strings to Key objects instead." %
                (qual(MockOldFactoryPrivateKeys),),
                factory.__file__, sshFactory.startFactory)
        self.assertEqual(sshFactory.privateKeys,
                          MockFactory().getPrivateKeys())
