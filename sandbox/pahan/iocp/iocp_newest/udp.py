import socket

from twisted.internet import interfaces, defer, main, error, protocol
from twisted.persisted import styles
from twisted.python import log, failure, reflect

from ops import ReadFileOp, WriteFileOp, WSARecvFromOp, WSASendToOp
from util import StateEventMachineType
import address

class Port(log.Logger, styles.Ephemeral, object):
    __metaclass__ = StateEventMachineType
    __implements__ = interfaces.IUDPTransport
    events = ["startListening", "stopListening", "write", "readDone", "readErr", "writeDone", "writeErr"]
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
        return "<%s on %s>" % (self.protocol.__class__, address.getPort(self.bindAddress, self.sockinfo))

    def handle_disconnected_startListening(self):
        self._bindSocket()
        self._connectSocket()

    def _bindSocket(self):
        log.msg("%s starting on %s" % (self.protocol.__class__, address.getPort(self.bindAddress, self.sockinfo)))
        try:
            skt = socket.socket(*self.sockinfo)
            skt.bind(self.bindAddress)
#            print "bound %s to %s" % (skt.fileno(), self.bindAddress)
        except socket.error, le:
            raise error.CannotListenError, (address.getHost(self.bindAddress, self.sockinfo), address.getPort(self.bindAddress, self.sockinfo), le)
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

    def handle_listening_readErr(self, ret, bytes):
        log.msg("read failed with err %s" % (ret,))
        # TODO: use Failures or something
        if ret == 1234: # ERROR_PORT_UNREACHABLE
            self.protocol.connectionRefused()
        if self.reading:
            self.startReading()

    def handle_disconnected_readErr(self, ret, bytes):
        pass # no kicking the dead horse

    def handle_disconnected_readDone(self, bytes, addr = None):
        pass # no kicking the dead horse

    def handle_listening_write(self, data, addr):
        self.performWrite(data, addr)

    def performWrite(self, data, addr = None):
        self.writing = True
        try:
            write_op = self.write_op_class(self)
            if addr:
                write_op.initiateOp(self.socket.fileno(), data, addr)
            else:
                write_op.initiateOp(self.socket.fileno(), data)
        except WindowsError, we:
            log.msg("initiating write failed with args %s" % (we,))

    def handle_listening_writeDone(self, bytes):
        log.msg("write success with bytes %s" % (bytes,))
#        self.callBufferHandlers(event = "buffer empty")

    def handle_listening_writeErr(self, ret, bytes):
        log.msg("write failed with err %s" % (ret,))
        self.connectionLost()

    def handle_disconnected_writeErr(self, ret, bytes):
        pass # no kicking the dead horse

    def handle_disconnected_writeDone(self, bytes):
        pass # no kicking the dead horse

    def writeSequence(self, seq):
        self.write("".join(seq))

    def handle_listening_stopListening(self):
        self.stopReading()
        self.connectionLost()

    def connectionLost(self, reason=None):
        log.msg('(Port %r Closed)' % address.getPort(self.bindAddress, self.sockinfo))
        self.protocol.doStop()
        self.socket.close()
        del self.socket
        self.state = "disconnected"

    def logPrefix(self):
        return self.logstr

    def getHost(self):
        return address.getFull(self.socket.getsockname(), self.sockinfo)

class ConnectedPort(Port):
    __implements__ = interfaces.IUDPConnectedTransport
    read_op_class = ReadFileOp
    write_op_class = WriteFileOp

    def __init__(self, addr, bindAddress, proto, maxPacketSize=8192):
        assert isinstance(proto, protocol.ConnectedDatagramProtocol)
        Port.__init__(self, bindAddress, proto, maxPacketSize)
        self.addr = addr
    
    def handle_disconnected_startListening(self):
        self._bindSocket()
        try:
            # TODO: do this properly
            self.socket.connect(self.addr)
        except socket.error, ce:
            self.protocol.connectionFailed(failure.Failure(error.DNSLookupError()))
            self.socket.close()
            del self.socket
        else:
            self._connectSocket()

    def handle_listening_write(self, data):
        self.performWrite(data)

    def getPeer(self):
        return address.getFull(self.socket.getpeername(), self.sockinfo)

