
import sha
import md5
import hmac
import time
import struct

def P_hash(hash, secret, seed, bytes):
    """Data expansion function.
    
    @type secret: C{str}
    @type seed: C{str}
    @type bytes: C{int}
    @rtype: C{str}
    """
    def A(i):
        if i == 0:
            return seed
        return hmac.hmac(secret, A(i - 1), hash).digest()
    n = 0
    r = ''
    while len(r) < bytes:
        n += 1
        r += hmac.hmac(secret, A(n) + seed, hash).digest()
    return r[:bytes]

def P_MD5(secret, seed, bytes):
    return P_hash(md5, secret, seed, bytes)

def P_SHA1(secret, seed, bytes):
    return P_hash(sha, secret, seed, bytes)

def dividedSecret(secret):
    """Divide a secret into two equal-length portions.
    
    @type secret: C{str}
    @rtype: 2 C{tuple} of C{str}
    """
    half = math.ceil(len(secret) / 2.0)
    if half % 2 == 0:
        return secret[:half], secret[half:]
    return secret[:half], secret[half-1:]

def XOR(A, B):
    return ''.join([chr(ord(a) ^ ord(b)) for (a, b) in zip(A, B)])

def PRF(secret, label, seed):
    S1, S2 = dividedSecret(secret)
    return XOR(P_MD5(S1, label + seed), P_SHA1(S2, label + seed))

class ConnectionState:
    """Describes the security parameters for a TLS Connection read or write state

    @ivar connectionEnd: Either SERVER_END or CLIENT_END - indicates which end of the
    TLS connection this side is considered.
    """
    
    SERVER_END = "server"
    CLIENT_END = "client"
    connectionEnd = None

    NULL = "null"
    RC4 = "rc4"
    RC2 = "rc2"
    DES = "des"
    DES3 = "3des"
    DES40 = "des40"
    bulkEncryptionAlgorithm = None

    MD5 = "md5"
    SHA = "sha"
    macAlgorithm = None

    compressionAlgorithm = None
    
    # 48 bytes of cryptographically secure goodness
    masterSecret = None
    
    # 32 byte value provided by the client
    clientRandom = None
    
    # 32 byte value provided by the server
    serverRandom = None
    
    # Groan
    exportable = None

    compressionState = None
    cipherState = None
    
    macSecret = None
    sequenceNumber = None    


class TLSRecordLayer:
    CHANGE_CIPHER_SPEC = 20
    ALERT = 21
    HANDSHAKE = 22
    APPLICATION_DATA = 23
    contentType = None

    # Two 8 bit unsigned integers indicating the protocol version
    version = (3, 1)

    maxFragmentSize = 2 ** 14

    # The data associated with this record
    fragment = None

    def __init__(self, contentType, bytes):
        self.contentType = contentType
        self.fragment = bytes

class TLSRecordLayerPacket:
    def __init__(self, type, version, fragment):
        self.type = type
        self.version = version
        self.fragment = fragment

    def encode(self):
        v1, v2 = self.version
        hdr = struct.pack('>BBBH', self.type, v1, v2, len(self.fragment))
        return hdr + self.fragment

class _PlaintextIterator:
    def __init__(self, record):
        self.contentType = record.contentType
        self.version = record.version
        self.bytes = record.fragment
        self.maxChunkSize = record.maxFragmentSize
        
    def next(self):
        if not self.bytes:
            raise StopIteration
        bytes = self.bytes[:self.maxChunkSize]
        self.bytes = self.bytes[self.maxChunkSize:]
        return TLSRecordLayerPacket(self.contentType, self.version, bytes)

class TLSPlaintext(TLSRecordLayer):
    """A packet of information on the TLS Record Layer
    """

    def __iter__(self):
        return _PlaintextIterator(self)


class TLSCompressed(TLSRecordLayer):
    """A packet of compressed information on the TLS Record Layer
    """

class TLSCiphertext(TLSRecordLayer):
    """
    """

    # Determines how fragment should be handled
    cipherType = None


def HMAC_hash(hash, writeSecret, seqNum, type, version, fragment):
    # seqNum is 64 bits
    assert seqNum < (2 ** 64)
    seqNum = struct.pack('>II', seqNum >> 32, seqNum & 0xffffffff)
    version = struct.pack('>BB', *version)
    length = struct.pack('>H', len(fragment))
    return hmac.hmac(writeSecret, seqNum + chr(contentType) + version + length + fragment, hash).digest()

class GenericCipher:
    def __init__(self, secParams, writeSecret, seqNum, contentType, version, fragment):
        self.mac = HMAC_hash(secParams.macAlgorithm, writeSecret, seqNum, contentType, version, fragment)

class StandardStreamCipher(GenericCipher):
    def __init__(self, secParams, writeSecret, seqNum, contentType, version, fragment):
        GenericCipher.__init__(self, secParams, writeSecret, seqNum, contentType, version, fragment)
        self.content = fragment

class GenericBlockCipher:
    blockSize = None

    def __init__(self, secParams, writeSecret, seqNum, contentType, version, fragment, padding=None):
        GenericCipher.__init__(self, secParams, writeSecret, seqNum, contentType, version, fragment)
        toEncode = self.mac + fragment
        if padding is None:
            padding = self.blockSize - (len(toEncode) % self.blockSize)
            if padding == self.blockSize:
                padding = 0
        self.content = cipher(toEncode + (chr(padding) * (padding + 1)))

class TLSHandshake(TLSRecordLayer):
    sessionIdentifier = None
    peerCertificate = None
    compressionMethod = None
    cipherSpec = None
    masterSecret = None
    isResumable = None

class CipherChange(TLSRecordLayer):
    CHANGE_CIPHER_SPEC = 1

class Alert(TLSRecordLayer):
    WARNING = 1
    FATAL = 2
    
    alertLevel = None
    
    CLOSE_NOTIFY = 0
    UNEXPECTED_MESSAGE = 10
    BAD_RECORD_MAC = 20
    DECRYPTION_FAILED = 21
    RECORD_OVERFLOW = 22
    DECOMPRESSION_FAILURE = 30
    HANDSHAKE_FAILURE = 40
    BAD_CERTIFICATE = 42
    UNSUPPORTED_CERTIFICATE = 32
    CERTIFICATE_REVOKED = 44
    CERTIFICATE_EXPIRED = 45
    CERTIFICATE_UNKNOWN = 46
    ILLEGAL_PARAMETER = 47
    UNKNOWN_CA = 48
    ACCESS_DENIED = 49
    DECODE_ERROR = 50
    DECRYPT_ERROR = 51
    EXPORT_RESTRICTION = 60
    PROTOCOL_VERSION = 70
    INSUFFICIENT_SECURITY = 71
    INTERNAL_ERROR = 80
    USER_CANCELED = 90 # SIC
    NO_RENEGOTIATION = 100
    
    alertDescription = None

class Handshake:
    CONTENT_TYPE = TLSRecordLayer.HANDSHAKE

    HELLO_REQUEST = 0
    CLIENT_HELLO = 1
    SERVER_HELLO = 2
    CERTIFICATE = 11
    SERVER_KEY_EXCHANGE = 12
    CERTIFICATE_REQUEST = 13
    SERVER_HELLO_DONE = 14
    CERTIFICATE_VERIFY = 165
    CLIENT_KEY_EXCHANGE = 16
    FINISHED = 20
    
    def __init__(self, type):
        self.handshakeType = type

    def encode(self):
        body = self.handshake_encode()
        assert len(body) < 2 ** 24
        high = len(body) >> 8
        low = len(body) & 0xff
        return struct.pack('>BHB', self.handshakeType, high, low) + body
    
class ClientHello(Handshake):
    def __init__(self, bytes):
        Handshake.__init__(self, Handshake.CLIENT_HELLO)
        self.gmt_unix_time = int(time.time())
        self.bytes = bytes
    
    def handshake_encode(self):
        return struct.pack('>I', self.gmt_unix_time) + self.bytes

import sys
sys.path.append('../../pahan/statefulprotocol')
from stateful import StatefulProtocol
class TLSClient(StatefulProtocol):
    currentReadState = None
    currentWriteState = None
    
    pendingReadState = None
    pendingWriteState = None

    protocolState = None

    buffer = ''

    CONTENT_TYPE_MAP = {chr(20): ('ChangeCipherSpec', 1),
                        chr(21): ('Alert', ),
                        chr(22): ('Handshake', ),
                        chr(23): ('ApplicationData', )}

    def write(self, packets):
        L = list(packets)
        bytes = [x.encode() for x in L]
        print 'Sending', repr(''.join(bytes))
        self.transport.writeSequence(bytes)

    def send(self, record):
        self.write(TLSPlaintext(record.CONTENT_TYPE, record.encode()))

    def getInitialState(self):
        return self.state_RecordType, 1

    def dataReceived(self, data):
        print 'Received', repr(data)
        StatefulProtocol.dataReceived(self, data)

    def connectionMade(self):
        self.send(ClientHello('x' * 28))

    def state_RecordType(self, data):
        method, length = self.CONTENT_TYPE_MAP[data]
        return getattr('rt_' + method), length
    state_RecordType.byteCount = 1

    def rt_ChangeCipherSpec(self, data):
        self.changeCipherSpec()
        return self.state_RecordType, self.state_RecordType.byteCount

    def rt_Alert(self, data):
        print 'Alert'

    def rt_Handshake(self, data):
        print 'Handshake'

    def rt_ApplicationData(self, data):
        print 'ApplicationData'

if __name__ == '__main__':
    from twisted.internet import ssl
    from twisted.internet import reactor
    from twisted.internet import protocol

    from twisted.python import log
    import sys
    log.startLogging(sys.stdout)

    sf = protocol.ServerFactory()
    cf = protocol.ClientFactory()
    cf2 = protocol.ClientFactory()

    sf.protocol = protocol.Protocol
    cf.protocol = TLSClient
    cf2.protocol = protocol.Protocol

    pem = '/home/exarkun/projects/python/Twisted/twisted/test/server.pem'
    port = reactor.listenSSL(0, sf, ssl.DefaultOpenSSLContextFactory(pem, pem), interface='127.0.0.1')
    conn = reactor.connectTCP('127.0.0.1', port.getHost()[2], cf)

    conn2 = reactor.connectSSL('127.0.0.1', port.getHost()[2], cf2, ssl.ClientContextFactory())

    reactor.callLater(1, reactor.stop)
    reactor.run()
    

    
