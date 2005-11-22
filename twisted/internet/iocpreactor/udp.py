# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import socket

from twisted.internet import interfaces, defer, error, protocol, address
from twisted.internet.abstract import isIPAddress
from twisted.persisted import styles
from twisted.python import log, failure, reflect

from ops import ReadFileOp, WriteFileOp, WSARecvFromOp, WSASendToOp
from util import StateEventMachineType
from zope.interface import implements

ERROR_PORT_UNREACHABLE = 1234

class Port(log.Logger, styles.Ephemeral, object):
    __metaclass__ = StateEventMachineType
    implements(interfaces.IUDPTransport)
    events = ["startListening", "stopListening", "write", "readDone", "readErr", "writeDone", "writeErr", "connect"]
    sockinfo = (socket.AF_INET, socket.SOCK_DGRAM, 0)
    read_op_class = WSARecvFromOp
    write_op_class = WSASendToOp
    reading = False
    # Actual port number being listened on, only set to a non-None
    # value when we are actually listening.
    _realPortNumber = None
    disconnected = property(lambda self: self.state == "disconnected")

    def __init__(self, bindAddress, proto, maxPacketSize=8192):
        assert isinstance(proto, protocol.DatagramProtocol)
        self.state = "disconnected"
        from twisted.internet import reactor
        self.bindAddress = bindAddress
        self._connectedAddr = None
        self.protocol = proto
        self.maxPacketSize = maxPacketSize
        self.logstr = reflect.qual(self.protocol.__class__) + " (UDP)"
        self.read_op = self.read_op_class(self)
        self.readbuf = reactor.AllocateReadBuffer(maxPacketSize)
        self.reactor = reactor
    
    def __repr__(self):
        if self._realPortNumber is not None:
            return "<%s on %s>" % (self.protocol.__class__, self._realPortNumber)
        else:
            return "<%s not connected>" % (self.protocol.__class__,)

    def handle_listening_connect(self, host, port):
        if not isIPAddress(host):
            raise ValueError, "please pass only IP addresses, not domain names"
        self.state = "connecting"
        return defer.maybeDeferred(self._connectDone, host, port)      

    def handle_connecting_connect(self, host, port):
        raise RuntimeError, "already connected, reconnecting is not currently supported (talk to itamar if you want this)"
    handle_connected_connect = handle_connecting_connect
        
    def _connectDone(self, host, port):
        self._connectedAddr = (host, port)
        self.state = "connected"
        self.socket.connect((host, port))
        return self._connectedAddr

    def handle_disconnected_startListening(self):
        self._bindSocket()
        host, port = self.bindAddress
        if isIPAddress(host):
             return defer.maybeDeferred(self._connectSocket, host)
        else:
            d = self.reactor.resolve(host)
            d.addCallback(self._connectSocket)
            return d

    def _bindSocket(self):
        try:
            skt = socket.socket(*self.sockinfo)
            skt.bind(self.bindAddress)
#            print "bound %s to %s" % (skt.fileno(), self.bindAddress)
        except socket.error, le:
            raise error.CannotListenError, (None, None, le)
        
        # Make sure that if we listened on port 0, we update that to
        # reflect what the OS actually assigned us.
        self._realPortNumber = skt.getsockname()[1]
        
        log.msg("%s starting on %s"%(self.protocol.__class__, self._realPortNumber))
        
        self.socket = skt

    def _connectSocket(self, host):
        self.bindAddress = (host, self.bindAddress[1])
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
        if ret == ERROR_PORT_UNREACHABLE:
            self.protocol.connectionRefused()
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
        log.msg('(Port %s Closed)' % self._realPortNumber)
        self._realPortNumber = None
        self.protocol.doStop()
        self.socket.close()
        del self.socket
        self.state = "disconnected"

    def logPrefix(self):
        return self.logstr

    def getHost(self):
        return address.IPv4Address('UDP', *(self.socket.getsockname() + ('INET_UDP',)))

