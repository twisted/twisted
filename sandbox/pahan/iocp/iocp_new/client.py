import socket

from twisted.persisted import styles
from twisted.internet.base import BaseConnector
from twisted.internet import defer, error
from twisted.python import failure

from abstract import ConnectedSocket
from ops import ConnectExOp
import address

class ClientSocket(ConnectedSocket):
    def __init__(self, sock, protocol, sf):
        ConnectedSocket.__init__(self, sock, protocol, sf)
        self.repstr = '<%s to %s at %x>' % (self.__class__, self.sf.addr, id(self))
        self.logstr = protocol.__class__.__name__+",client"
        self.startReading()

    def handleDead(self, reason):
        ConnectedSocket.handleDead(self, reason)
        self.sf.cleanMeUp()
        self.sf.connectionLost(reason)

class SocketConnector(BaseConnector):
    real_transport = ClientSocket
    af = None
    type = None
    proto = None
    addr = None
    bindAddress = None
    connect_op = ConnectExOp
    def __init__(self, addr, factory, timeout, bindAddress, **kw):
        from twisted.internet import reactor
        BaseConnector.__init__(self, factory, timeout, reactor)
        self.addr = addr
        self.bindAddress = bindAddress
        self.kw = kw

    def _makeTransport(self):
        self.startConnecting()
        return self

    def prepareAddress(self):
        raise NotImplementedError

    def checkIfStopConnecting(self, err, l):
        if l != []:
            return
        self.cleanMeUp()
        self.connectionFailed(err)

    def startConnecting(self):
        d = defer.maybeDeferred(self.prepareAddress)
        self.stop_flag = []
        d.addCallback(self.resolveDone, self.stop_flag)
        d.addErrback(self.checkIfStopConnecting, self.stop_flag)

    def resolveDone(self, addr, l):
        if l != []:
            return
        try:
            skt = socket.socket(self.af, self.type, self.proto)
        except socket.error, se:
            raise error.ConnectBindError(se[0], se[1])
        try:
            if self.bindAddress is None:
                self.bindAddress = ("", 0)
            skt.bind(self.bindAddress)
        except socket.error, se:
            raise error.ConnectBindError(se[0], se[1])
        self.socket = skt
        op = self.connect_op()
        op.initiateOp(self.socket, addr)
        op.addCallback(self.connectDone, self.stop_flag)
        op.addErrback(self.checkIfStopConnecting, self.stop_flag)

    def connectDone(self, v, l):
        if l != []:
            return
        p = self.buildProtocol(self.socket.getpeername())
        self.sock_transport = self.real_transport(self.socket, p, self)
        p.makeConnection(self.sock_transport)
        del self.stop_flag

    def failIfNotConnected(self, err):
        self.cleanMeUp()
        self.connectionFailed(failure.Failure(err))

    def cleanMeUp(self):
        if hasattr(self, "stop_flag"):
            self.stop_flag.append(None)
            del self.stop_flag
        if hasattr(self, "socket"):
            self.socket.close()
            del self.socket
        if hasattr(self, "sock_transport"):
            del self.sock_transport

    def getDestination(self):
        return address.getFull(self.addr, self.af, self.type, self.proto)

    def loseConnection(self):
        self.sock_transport.loseConnection()

