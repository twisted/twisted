import socket

from twisted.internet import interfaces, defer, main, error, protocol, address
from twisted.internet.abstract import isIPAddress
from twisted.persisted import styles
from twisted.python import log, failure, reflect

from ops import ReadFileOp, WriteFileOp, WSARecvFromOp, WSASendToOp
from util import StateEventMachineType

class Port(log.Logger, styles.Ephemeral, object):
    __metaclass__ = StateEventMachineType
    __implements__ = interfaces.IUDPTransport
    events = ["startListening", "stopListening", "write", "readDone", "readErr", "writeDone", "writeErr", "connect"]
    sockinfo = (socket.AF_INET, socket.SOCK_DGRAM, 0)
    read_op_class = WSARecvFromOp
    write_op_class = WSASendToOp
    reading = False

    def __init__(self, bindAddress, proto, maxPacketSize=8192):
        assert isinstance(proto, protocol.DatagramProtocol)
        self.state = "disconnected"
        from twisted.internet import reactor
        self.bindAddress = bindAddress
        self.protocol = proto
        self.maxPacketSize = maxPacketSize
        self.logstr = reflect.qual(self.protocol.__class__) + " (UDP)"
        self.read_op = self.read_op_class(self)
        self.readbuf = reactor.AllocateReadBuffer(maxPacketSize)
        self.reactor = reactor

    def __repr__(self):
        return "<%s on %s>" % (self.protocol.__class__, 'port')

    def handle_listening_connect(self, host, port):
        self.state = "connecting"
        if isIPAddress(host):
             return defer.maybeDeferred(self._connectDone, host, port)
        else:
            d = self.reactor.resolve(host)
            d.addCallback(self._connectDone, port)
            return d        

    def _connectDone(self, host, port):
        self._connectedAddr = (host, port)
        self.state = "connected"
        self.socket.connect((host, port))
        return self._connectedAddr

    def handle_disconnected_startListening(self):
        self._bindSocket()
        self._connectSocket()

    def _bindSocket(self):
        log.msg("%s starting on %s" % (self.protocol.__class__, 'port'))
        try:
            skt = socket.socket(*self.sockinfo)
            skt.bind(self.bindAddress)
#            print "bound %s to %s" % (skt.fileno(), self.bindAddress)
        except socket.error, le:
            raise error.CannotListenError, (None, None, le)
        self.socket = skt

    def _connectSocket(self):
        self.protocol.makeConnection(self)
        self.startReading()
        self.state = "listening"

    def startReading(self):
        self.reading = True
        try:
            self.read_op.initiateOp(self.socket.fileno(), self.readbuf)
        except WindowsError, we:
            log.msg("initiating read failed with args %s" % (we,))

    def stopReading(self):
        self.reading = False

    def handle_listening_readDone(self, bytes, addr = None):
        if addr:
            self.protocol.datagramReceived(self.readbuf[:bytes], addr)
        else:
            self.protocol.datagramReceived(self.readbuf[:bytes])
        if self.reading:
            self.startReading()
    handle_connecting_readDone = handle_listening_readDone
    handle_connected_readDone = handle_listening_readDone

    def handle_listening_readErr(self, ret, bytes):
        log.msg("read failed with err %s" % (ret,))
        # TODO: use Failures or something
        if ret == 1234: # ERROR_PORT_UNREACHABLE
            self.protocol.connectionRefused()
        if self.reading:
            self.startReading()
    handle_connecting_readErr = handle_listening_readErr
    handle_connected_readErr = handle_listening_readErr

    def handle_disconnected_readErr(self, ret, bytes):
        pass # no kicking the dead horse

    def handle_disconnected_readDone(self, bytes, addr = None):
        pass # no kicking the dead horse

    def handle_listening_write(self, data, addr):
        self.performWrite(data, addr)

    def handle_connected_write(self, data, addr = None):
        assert addr in (None, self._connectedAddr)
        self.performWrite(data, addr)

    def performWrite(self, data, addr = None):
#        print "performing write on", data, addr
        self.writing = True
        try:
            write_op = self.write_op_class(self)
            if not addr:
                addr = self._connectedAddr
            write_op.initiateOp(self.socket.fileno(), data, addr)
#            print "initiating write_op to", addr
        except WindowsError, we:
            log.msg("initiating write failed with args %s" % (we,))

    def handle_listening_writeDone(self, bytes):
        log.msg("write success with bytes %s" % (bytes,))
#        self.callBufferHandlers(event = "buffer empty")
    handle_connecting_writeDone = handle_listening_writeDone
    handle_connected_writeDone = handle_listening_writeDone

    def handle_listening_writeErr(self, ret, bytes):
        log.msg("write failed with err %s" % (ret,))
        self.connectionLost()
    handle_connecting_writeErr = handle_listening_writeErr
    handle_connected_writeErr = handle_listening_writeErr

    def handle_disconnected_writeErr(self, ret, bytes):
        pass # no kicking the dead horse

    def handle_disconnected_writeDone(self, bytes):
        pass # no kicking the dead horse

    def writeSequence(self, seq, addr):
        self.write("".join(seq), addr)

    def handle_listening_stopListening(self):
        self.stopReading()
        self.connectionLost()
    handle_connecting_stopListening = handle_listening_stopListening
    handle_connected_stopListening = handle_listening_stopListening

    def connectionLost(self, reason=None):
        log.msg('(Port %r Closed)' % ('port',))
        self.protocol.doStop()
        self.socket.close()
        del self.socket
        self.state = "disconnected"

    def logPrefix(self):
        return self.logstr

    def getHost(self):
        return address.IPv4Address('UDP', *(self.socket.getsockname() + ('INET_UDP',)))

