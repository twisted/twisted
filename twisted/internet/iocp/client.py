import socket

from twisted.persisted import styles
from twisted.internet.base import BaseConnector
from twisted.internet import defer, interfaces
from twisted.python import failure

from abstract import ConnectedSocket
from ops import ConnectExOp
from util import StateEventMachineType
import error

class ClientSocket(ConnectedSocket):
    def __init__(self, sock, protocol, sf):
        ConnectedSocket.__init__(self, sock, protocol, sf)
        self.repstr = '<%s to %s at %x>' % (self.__class__, self.sf.addr, id(self))
        self.logstr = protocol.__class__.__name__+",client"
        self.startReading()

class _SubConnector:
    state = "connecting"
    socket = None
    def __init__(self, sf):
        self.sf = sf

    def startConnecting(self):
        d = defer.maybeDeferred(self.sf.prepareAddress)
        d.addCallback(self._cbResolveDone)
        d.addErrback(self._ebResolveErr)

    def _cbResolveDone(self, addr):
        if self.state == "dead":
            return

        try:
            skt = socket.socket(*self.sf.sockinfo)
        except socket.error, se:
            raise error.ConnectBindError(se[0], se[1])
        try:
            if self.sf.bindAddress is None:
                self.sf.bindAddress = ("", 0) # necessary for ConnectEx
            skt.bind(self.sf.bindAddress)
        except socket.error, se:
            raise error.ConnectBindError(se[0], se[1])
        self.socket = skt
        op = ConnectExOp(self)
        op.initiateOp(self.socket, addr)

    def _ebResolveErr(self, fail):
        if self.state == "dead":
            return

        self.sf.connectionFailed(fail)

    def connectDone(self):
        if self.state == "dead":
            return

        self.sf.connectionSuccess()

    def connectErr(self, err):
        if self.state == "dead":
            return

        self.sf.connectionFailed(err)

class SocketConnector(styles.Ephemeral, object):
    __metaclass__ = StateEventMachineType
    __implements__ = interfaces.IConnector
    transport = ClientSocket
    events = ["stopConnecting", "disconnect", "connect"]
    sockinfo = None
    factoryStarted = False
    timeoutID = None
    def __init__(self, addr, factory, timeout, bindAddress):
        from twisted.internet import reactor
        self.state = "disconnected"
        self.addr = addr
        self.factory = factory
        self.timeout = timeout
        self.bindAddress = bindAddress
        self.reactor = reactor

    def handle_connecting_stopConnecting(self):
        self.connectionFailed(failure.Failure(error.UserError()))

    def handle_disconnected_stopConnecting(self):
        raise error.NotConnectingError

    handle_connected_stopConnecting = handle_disconnected_stopConnecting

    handle_connecting_disconnect = handle_connecting_stopConnecting

    def handle_connected_disconnect(self):
        self.transport_obj.loseConnection()

    def handle_disconnected_connect(self):
        self.state = "connecting"
        if not self.factoryStarted:
            self.factory.doStart()
            self.factoryStarted = True

        if self.timeout is not None:
            self.timeoutID = self.reactor.callLater(self.timeout, self.connectionFailed, failure.Failure(error.TimeoutError()))

        self.sub = _SubConnector(self)
        self.sub.startConnecting()

        self.factory.startedConnecting(self)

    def prepareAddress(self):
        raise NotImplementedError

    def connectionLost(self, reason):
        self.state = "disconnected"
        self.factory.clientConnectionLost(self, reason)
        if self.state == "disconnected":
            # factory hasn't called our connect() method
            self.factory.doStop()
            self.factoryStarted = 0

    def connectionFailed(self, reason):
        if self.sub.socket:
            self.sub.socket.close()
        self.sub.state = "dead"
        del self.sub
        self.state = "disconnected"
        self.cancelTimeout()
        self.factory.clientConnectionFailed(self, reason)
        if self.state == "disconnected":
            # factory hasn't called our connect() method
            self.factory.doStop()
            self.factoryStarted = 0

    def cancelTimeout(self):
        if self.timeoutID:
            try:
                self.timeoutID.cancel()
            except ValueError:
                pass
            del self.timeoutID

    def connectionSuccess(self):
        socket = self.sub.socket
        self.sub.state = "dead"
        del self.sub
        self.state = "connected"
        self.cancelTimeout()
        p = self.factory.buildProtocol(self.buildAddress(socket.getpeername()))
        self.transport_obj = self.transport(socket, p, self)
        p.makeConnection(self.transport_obj)

