
import time
import struct

import crypt

from twisted.python import context
from twisted.python import components

# Record Layer Content Types
RL_CT_CHANGE_CIPHER_SPEC = 20
RL_CT_ALERT = 21
RL_CT_HANDSHAKE = 22
RL_CT_APPLICATION_DATA = 23

def twos(s):
    return zip(*[iter(s)] * 2)

class IEncodable(components.Interface):
    def encode(self):
        """Encode this record fully for transmission.
        """

class Random:
    __implements__ = (IEncodable,)

    def __init__(self, tstamp=None, rbytes=None):
        self.time = tstamp or int(time.time())
        self.bytes = rbytes or crypt.getRandomBytes(28)

    def encode(self):
        return struct.pack('>I', self.time) + self.bytes

def NullCipherMethod(record):
    return record
def NullCompressionMethod(record):
    return record

class SecurityParameters(object):
    macAlgorithm = staticmethod(crypt.HMAC_NULL)
    bulkEncryptionAlgorithm = staticmethod(NullCipherMethod)
    compressionAlgorithm = staticmethod(NullCompressionMethod)

    masterSecret = None
    clientRandom = None
    serverRandom = None

    def getCipherSuites(self):
        return [0]

    def getCompressionMethods(self):
        return [0]

# Handshake Content Types
HS_CT_HELLO_REQUEST = 0
HS_CT_CLIENT_HELLO = 1
HS_CT_SERVER_HELLO = 2
HS_CT_CERTIFICATE = 11
HS_CT_SERVER_KEY_EXCHANGE = 12
HS_CT_CERTIFICATE_REQUEST = 13
HS_CT_SERVER_HELLO_DONE = 14
HS_CT_CERTIFICATE_VERIFY = 15
HS_CT_CLIENT_KEY_EXCHANGE = 16
HS_CT_FINISHED = 20

def logbytes(name, bytes):
    print name, len(bytes), ':', ' '.join(map(''.join, zip(*[iter(bytes.encode('hex'))] * 2)))


class RecordLayer(object):
    MAX_FRAGMENT_SIZE = 2 ** 14

    def __init__(self, record):
        self.record = record

    def encode(self):
        S = self.MAX_FRAGMENT_SIZE
        packets = []
        bytes = self.record.encode()
        hdr = struct.pack('>BBB', self.record.type, *self.record.version)
        while bytes:
            toenc, bytes = bytes[:S], bytes[S:]
            packets.append(hdr + struct.pack('>H', len(toenc)) + toenc)
        logbytes('Record Layer', ''.join(packets))
        return ''.join(packets)

class Plaintext(object):
    def __init__(self, record):
        self.type = record.type
        self.version = record.version
        self.record = record

    def encode(self):
        r = self.record.encode()
        logbytes('Plaintext', r)
        return r

class Handshake(object):

    type = RL_CT_HANDSHAKE
    version = (3, 1)

    handshakeType = None
    def encode(self):
        body = self.handshake_encode()
        assert len(body) < 2 ** 24
        high = len(body) >> 8
        low = len(body) & 0xff
        r = struct.pack('>BHB', self.handshakeType, high, low) + body
        logbytes('Handshake', r)
        return r

class ClientHello(Handshake):
    version = (3, 1)
    handshakeType = HS_CT_CLIENT_HELLO

    def __init__(self, version, random, session_id, ciphers, compressors):
        self.version = version
        self.random = random
        self.sessionID = session_id
        self.ciphers = ciphers
        self.compressors = compressors
    
    def handshake_encode(self):
        ver = ''.join(map(chr, self.version))
        rand = self.random.encode()
        sess = chr(len(self.sessionID)) + self.sessionID
        ciph = ''.join([struct.pack('>H', c) for c in self.ciphers])
        ciph = struct.pack('>H', len(ciph)) + ciph
        comp = chr(len(self.compressors)) + ''.join(map(chr, self.compressors))
        r = ver + rand + sess + ciph + comp
        logbytes('ClientHello', r)
        return r

class ServerHello(ClientHello):
    handshakeType = HS_CT_SERVER_HELLO

class Certificate(Handshake):
    handshakeType = HS_CT_CERTIFICATE

    def handshake_encode(self):
        pass

import sys
sys.path.append('../../pahan/statefulprotocol')
from stateful import StatefulProtocol
class RecordProtocol(StatefulProtocol):
    currentReadSecurity = None
    currentWriteSecurity = None
    
    pendingReadSecurity = None
    pendingWriteSecurity = None

    def connectionMade(self):
        for cp in ('pending', 'current'):
            for rw in ('Read', 'Write'):
                setattr(self, cp + rw + 'Security', SecurityParameters())

    def _write(self, record):
        comp = self.currentWriteSecurity.compressionAlgorithm
        ciph = self.currentWriteSecurity.bulkEncryptionAlgorithm
        bytes = RecordLayer(ciph(comp(record))).encode()
        logbytes('Sending', bytes)
        self.transport.write(bytes)

    def send(self, record):
        ctx = {'SecurityParameters': self.currentWriteSecurity}
        rec = Plaintext(record)
        context.call(ctx, self._write, rec)    

class TLSClient(RecordProtocol):

    buffer = ''

    CONTENT_TYPE_MAP = {chr(20): 'ChangeCipherSpec',
                        chr(21): 'Alert',
                        chr(22): 'Handshake',
                        chr(23): 'ApplicationData'}

    def getInitialState(self):
        m = self.state_RecordType
        return m, m.byteCount

    def dataReceived(self, data):
        print 'Received', repr(data)
        StatefulProtocol.dataReceived(self, data)

    def connectionMade(self):
        RecordProtocol.connectionMade(self)
        sp = getattr(self, cp + rw + 'Security')
        cipherSuites = sp.getCipherSuites()
        compMethods = sp.getCompressionMethods()
        self.send(ClientHello((3, 1), Random(), '', cipherSuites, compMethods))

    def state_RecordType(self, data):
        method = self.CONTENT_TYPE_MAP[data]
        method = getattr(self, 'rt_' + method)
        return method, method.byteCount
    state_RecordType.byteCount = 1

    def rt_ChangeCipherSpec(self, data):
        self.changeCipherSpec()
        return self.state_RecordType, self.state_RecordType.byteCount
    rt_ChangeCipherSpec.byteCount = 1

    def rt_Alert(self, data):
        print 'Alert'

    def rt_Handshake(self, data):
        print 'Handshake'

    def rt_ApplicationData(self, data):
        print 'ApplicationData'

class TLSServerProtocol(RecordProtocol):

    CONTENT_TYPE_MAP = {chr(20): 'ChangeCipherSpec',
                        chr(21): 'Alert',
                        chr(22): 'Handshake',
                        chr(23): 'ApplicationData'}

    HANDSHAKE_TYPE_MAP = {chr(0): 'HelloRequest',
                          chr(1): 'ClientHello',
                          chr(2): 'ServerHello',
                          chr(11): 'Certificate',
                          chr(12): 'ServerKeyExchange',
                          chr(13): 'CertificateRequest',
                          chr(14): 'ServerHelloDone',
                          chr(15): 'CertificateVerify',
                          chr(16): 'ClientKeyExchange',
                          chr(20): 'HandshakeFinished'}

    def dataReceived(self, bytes):
        logbytes("Server Received", bytes)
        StatefulProtocol.dataReceived(self, bytes)

    def getInitialState(self):
        m = self.state_RecordTypeAndVersionAndLength
        return m, m.byteCount

    def state_RecordTypeAndVersionAndLength(self, data):
        logbytes("RTAV", data)
        recordType = data[0]
        self.recordVersion = map(ord, data[1:3])
        recordLength = struct.unpack('>H', data[3:])[0]
        print 'Version is', self.recordVersion
        m = getattr(self, "rt_" + self.CONTENT_TYPE_MAP[recordType])
        print 'Next state is', m, recordLength
        return m, m.byteCount
    state_RecordTypeAndVersionAndLength.byteCount = 5

    def rt_Handshake(self, data):
        logbytes("Handshake", data)
        # Determine the type of handshake record this is
        m = getattr(self, 'hs_' + self.HANDSHAKE_TYPE_MAP[data[0]])
        bytes = struct.unpack('>I', '\0' + data[1:4])[0]
        print 'Next state is', m, bytes
        return m, bytes
    rt_Handshake.byteCount = 4

    def rt_Alert(self, data):
        print 'Alert!', data

    def hs_HelloRequest(self, data):
        logbytes("HelloRequest", data)
        print 'whaaaat'
        pass

    def hs_ClientHello(self, data):
        logbytes("ClientHello", data)
        fmt = '>BBI28spH'
        L = struct.calcsize(fmt)
        front, data = data[:L], data[L:]
        cv1, cv2, time, random, sessionID, nCiphs = struct.unpack(fmt, front)
        logbytes("Ciphers", data)
        ciphs, data = data[:nCiphs], data[nCiphs:]
        ciphers = [ord(a) << 8 | ord(b) for (a, b) in twos(ciphs)]
        nComps = ord(data[0])
        compressors = map(ord, data[1:nComps+1])
        ch = ClientHello((3, 1), Random(time, random), sessionID, ciphers, compressors)
        self.handshakeMessage(ch)
        m = self.state_RecordTypeAndVersionAndLength
        return m, m.byteCount
    

class TLSServer(TLSServerProtocol):
    sessions = {}

    def generateSessionID(self):
        return 'sessionID'

    def handshakeMessage(self, msg):
        f = self.HANDSHAKE_TYPE_MAP[chr(msg.handshakeType)]
        return getattr(self, 'handshake_' + f)(msg)

    def handshake_ClientHello(self, msg):
        if msg.sessionID in self.sessions:
            return self.resumeSession(msg)
        # XXX Check timestamp
        self.pendingWriteSecurity.clientRandom = msg.random.bytes
        self.pendingReadSecurity.clientRandom = msg.random.bytes

        random = crypt.getRandomBytes(28)
        self.pendingWriteSecurity.serverRandom = random
        self.pendingReadSecurity.serverRandom = random

        sp = self.currentWriteSecurity

        sessionID = self.generateSessionID()
        cs = sp.getCipherSuites()
        cm = sp.getCompressionMethods()
        h = ServerHello((3, 1), Random(rbytes=random), sessionID, cs, cm)
        self.send(h)
        c = Certificate()
        self.send(c)
        

if __name__ == '__main__':
    from twisted.internet import ssl
    from twisted.internet import reactor
    from twisted.internet import protocol

    from twisted.python import log
    import sys
    log.startLogging(sys.stdout)

    class ClientContextFactory(ssl.ClientContextFactory):
        method = ssl.SSL.TLSv1_METHOD

    class HexBytePrintingProtocol(protocol.Protocol):
        def dataReceived(self, bytes):
            logbytes("Received", bytes)

    OpenSSLServerFactory = protocol.ServerFactory()
    OpenSSLServerFactory.protocol = protocol.Protocol

    OpenSSLClientFactory = protocol.ClientFactory()
    OpenSSLClientFactory.protocol = protocol.Protocol

    PlainServerFactory = protocol.ServerFactory()
    PlainServerFactory.protocol = HexBytePrintingProtocol

    PlainClientFactory = protocol.ClientFactory()
    PlainClientFactory.protocol = HexBytePrintingProtocol

    PythonTLSServerFactory = protocol.ServerFactory()
    PythonTLSServerFactory.protocol = TLSServer

    PythonTLSClientFactory = protocol.ClientFactory()
    PythonTLSClientFactory.protocol = TLSClient

    pem = '/home/exarkun/projects/python/Twisted/twisted/test/server.pem'
    OpenSSLPort = reactor.listenSSL(0, OpenSSLServerFactory, ssl.DefaultOpenSSLContextFactory(pem, pem), interface='127.0.0.1')
    PlainPort = reactor.listenTCP(0, PlainServerFactory)
    PythonTLSPort = reactor.listenTCP(0, PythonTLSServerFactory)

    OpenSSLConn = reactor.connectSSL('127.0.0.1', PythonTLSPort.getHost()[2], OpenSSLClientFactory, ClientContextFactory())

    # PythonTLSConn = reactor.connectTCP('127.0.0.1', OpenSSLPort.getHost()[2], PythonTLSClientFactory)

    reactor.callLater(1, reactor.stop)
    reactor.run()
