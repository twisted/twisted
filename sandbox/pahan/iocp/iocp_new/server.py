import socket

from twisted.persisted import styles
from twisted.python import reflect, log
from twisted.internet import protocol, defer, main

from abstract import ConnectedSocket, RWHandle
from ops import AcceptExOp, WSARecvFromOp, WSASendToOp, ReadFileOp, WriteFileOp
import address, error
import iocpdebug

class ServerSocket(ConnectedSocket):
    def __init__(self, sock, protocol, sf, sessionno):
        ConnectedSocket.__init__(self, sock, protocol, sf)
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno,
                address.getHost(self.sf.addr, self.sf.af, self.sf.type, self.sf.proto))
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, sessionno, 
                address.getPort(self.sf.addr, self.sf.af, self.sf.type, self.sf.proto))
        self.startReading()

class SocketPort(styles.Ephemeral):
    transport = ServerSocket
    accept_op = AcceptExOp
    af = None
    type = None
    proto = None
    accepting = 0
    disconnected = 0
    sessionno = 0
    addr = None
    factory = None
    backlog = None
    def __init__(self, addr, factory, backlog, **kw):
        self.addr = addr
        self.factory = factory
        self.backlog = backlog
        self.kw = kw

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, address.getPort(self.addr, self.af, self.type, self.proto))

    def startListening(self):
        log.msg("%s starting on %s" % (self.factory.__class__, address.getPort(self.addr, self.af, self.type, self.proto)))
        try:
            skt = socket.socket(self.af, self.type, self.proto)
            skt.bind(self.addr)
        except socket.error, le:
            raise error.CannotListenError, (self.addr, le)
        self.factory.doStart()
        skt.listen(self.backlog)
        self.accepting = 1
        self.socket = skt
        self.startAccepting()

    def startAccepting(self):
        op = self.accept_op()
        op.initiateOp(self.socket)
        op.addCallback(self.acceptDone)
        op.addErrback(self.acceptErr)

    def acceptDone(self, (sock, addr)):
        if self.accepting:
            protocol = self.factory.buildProtocol(addr)
            if protocol is None:
                sock.close()
            else:
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(sock, protocol, self, s)
                protocol.makeConnection(transport)
            self.startAccepting()
        else:
            sock.close()

    def acceptErr(self, err):
        if iocpdebug.debug:
            print "acceptErr", err
            err.printTraceback()
        if isinstance(err, error.NonFatalException):
            self.startAccepting() # delay or just fail?
        else:
            if not self.disconnected:
                self.stopListening()

    def stopListening(self):
        self.disconnected = 1
        self.stopAccepting()
        self.socket.close()
        log.msg('(Port %r Closed)' % address.getPort(self.addr, self.af, self.type, self.proto))
        self.factory.doStop()

    def stopAccepting(self):
        self.accepting = 0

#    loseConnection = stopListening

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)

    def getHost(self):
        return address.getFull(self.socket.getsockname(), self.af, self.type, self.proto)

    def getPeer(self):
        return address.getFull(self.socket.getpeername(), self.af, self.type, self.proto)

# refactor me later to reuse ConnectedPort
class DatagramPort(RWHandle):
    af = None
    type = None
    proto = None
    read_op = WSARecvFromOp
    write_op = WSASendToOp

    def __init__(self, addr, proto, maxPacketSize=8192):
        RWHandle.__init__(self)
        assert isinstance(proto, protocol.DatagramProtocol)
        self.addr = addr
        self.protocol = proto
        self.maxPacketSize = maxPacketSize
        self.logstr = "%s (%s)" % (reflect.qual(self.protocol.__class__), address.getShortProtoName(self.af, self.type, self.proto))

    def __repr__(self):
        return "<%s on %s>" % (self.protocol.__class__, address.getPort(self.addr, self.af, self.type, self.proto))

    def startListening(self):
        self._bindSocket()
        self._connectToProtocol()
    
    def _bindSocket(self):
        log.msg("%s starting on %s" % (self.protocol.__class__, address.getPort(self.addr, self.af, self.type, self.proto)))
        try:
            skt = socket.socket(self.af, self.type, self.proto)
            skt.bind(self.addr)
        except socket.error, le:
            raise error.CannotListenError, (self.addr, le)
        self.connected = 1
        self.socket = skt
        self.handle = skt.fileno()
    
    def _connectToProtocol(self):
        self.protocol.makeConnection(self)
        self.startReading()

    def writeSequence(self, iovec, addr):
        self.write("".join(iovec), addr)

    def loseConnection(self):
        self.stopWorking(main.CONNECTION_DONE)
        if self.connected:
            from twisted.internet import reactor
            reactor.callLater(0, self.handleDead)

    def stopListening(self):
        if self.connected:
            result = self.d = defer.Deferred()
        else:
            result = None
        self.loseConnection()
        return result
    
    def handleDead(self, reason):
        log.msg('(Port %s Closed)' % address.getPort(self.addr, self.af, self.type, self.proto))
        if hasattr(self, "protocol"):
            # we won't have attribute in ConnectedPort, in cases
            # where there was an error in connection process
            self.protocol.doStop()
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.handle
        if hasattr(self, "d"):
            self.d.callback(None)
            del self.d

    def getHost(self):
        return address.getFull(self.socket.getsockname(), self.af, self.type, self.proto)


class ConnectedDatagramPort(DatagramPort):
    read_op = ReadFileOp
    write_op = WriteFileOp
    def __init__(self, addr, remoteaddr, proto, maxPacketSize=8192):
        assert isinstance(proto, protocol.ConnectedDatagramProtocol)
        DatagramPort.__init__(self, addr, proto, maxPacketSize)
        self.remoteaddr = remoteaddr
    
    def prepareAddress(self):
        raise NotImplementedError

    def startListening(self):
        self._bindSocket()
        self.realAddress = None
        d = defer.maybeDeferred(self.prepareAddress())
        d.addCallback(self.setRealAddress).addErrback(self.connectionFailed)

    def setRealAddress(self, addr):
        self.realAddress = addr
        self.socket.connect((self.addr))
        self._connectToProtocol()
    
    def connectionFailed(self, reason):
        self.loseConnection()
        self.protocol.connectionFailed(reason)
        del self.protocol

    def getPeer(self):
        return address.getFull(self.socket.getpeername(), self.af, self.type, self.proto)

