
import struct

from twisted.python import context
from twisted.python import components

class IEncodable(components.Interface):
    def encode(self):
        pass

class TLSRecordLayer:
    CHANGE_CIPHER_SPEC = 20
    ALERT = 21
    HANDSHAKE = 22
    APPLICATION_DATA = 23

    # Two 8 bit unsigned integers indicating the protocol version
    version = (3, 1)

    maxFragmentSize = 2 ** 14

    # The data associated with this record
    fragment = None

    def __init__(self, record):
        self.type = record.type
        self.version = record.version
        self.fragment = record.fragment

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
    TLSRecordLayerPacketType = TLSRecordLayerPacket
    
    def __init__(self, record):
        self.type = record.type
        self.version = record.version
        self.bytes = record.fragment
        self.maxChunkSize = record.maxFragmentSize
        
    def next(self):
        if not self.bytes:
            raise StopIteration
        bytes = self.bytes[:self.maxChunkSize]
        self.bytes = self.bytes[self.maxChunkSize:]
        return self.TLSRecordLayerPacketType(self.type, self.version, bytes)

class TLSPlaintext(TLSRecordLayer):
    """A packet of information on the TLS Record Layer
    """
    IteratorType = _PlaintextIterator

    def __iter__(self):
        return self.IteratorType(self)

class NullCompressionMethod(TLSRecordLayer):
    """A packet of uncompressed compressed information on the TLS Record Layer
    """

class TLSRecordLayerNullCipherPacket(TLSRecordLayerPacket):
    def encode(self):
        f = self.fragment
        sp = context.get('SecurityParameters')
        mac = sp.macAlgorithm(sp.writeSecret, sp.seqNum(), self.type, self.version, f)
        hdr = struct.pack('>BBBH', self.type, v1, v2, len(f) + len(mac))
        return hdr + f + mac
        
class _CiphertextIterator:
    TLSRecordLayerPacketType = TLSRecordLayerNullCipherPacket

class NullCipherMethod(TLSRecordLayer):
    IteratorType = _CiphertextIterator

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

class SecurityParameters:
    """Describes the security parameters for a TLS Connection read or write state

    @ivar connectionEnd: Either SERVER_END or CLIENT_END - indicates which end of the
    TLS connection this side is considered.
    """
    
    SERVER_END = "server"
    CLIENT_END = "client"
    connectionEnd = None

    bulkEncryptionAlgorithm = NullCipherMethod
    macAlgorithm = HMAC_NULL
    compressionAlgorithm = NullCompressionMethod
    
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
    sequenceNumber = -1

    def seqNum(self):
        self.sequenceNumber += 1
        return self.sequenceNumber

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

