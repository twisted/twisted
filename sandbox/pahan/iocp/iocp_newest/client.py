import socket

from twisted.persisted import styles
from twisted.internet.base import BaseConnector
from twisted.internet import defer, error, interfaces
from twisted.python import failure

from abstract import ConnectedSocket
from ops import ConnectExOp
from util import StateEventMachineType
import address

class ClientSocket(ConnectedSocket):
    def __init__(self, sock, protocol, sf):
        ConnectedSocket.__init__(self, sock, protocol, sf)
        self.repstr = '<%s to %s at %x>' % (self.__class__, self.sf.addr, id(self))
        self.logstr = protocol.__class__.__name__+",client"
        self.startReading()

class SocketConnector(styles.Ephemeral):
    __metaclass__ = StateEventMachineType
    __implements__ = interfaces.IConnector
    transport = ClientSocket
    events = ["stopConnecting", "disconnect", "connect", "connectDone", "connectErr"]
    sockinfo = None
    factoryStarted = False
    def __init__(self, address, factory, timeout):
        from twisted.internet import reactor
        self.state = "disconnected"
        self.address = address
        self.factory = factory
        self.timeout = timeout
        self.reactor = reactor

    def handle_connecting_stopConnecting(self):
        self.state = "disconnected"
        self.socket.close()

    handle_connecting_disconnect = handle_connecting_stopConnecting

    def handle_connected_disconnect(self):
        self.transport_obj.loseConnection()

    def handle_disconnected_connect(self):
        self.state = "connecting"
        if not self.factoryStarted:
            self.factory.doStart()
            self.factoryStarted = True
        self.transport = transport = self._makeTransport()
        if self.timeout is not None:
            self.timeoutID = self.reactor.callLater(self.timeout, transport.failIfNotConnected, error.TimeoutError())
        self.factory.startedConnecting(self)


    def handle_connecting_connectDone(self):
        pass

    def handle_connecting_connectErr(self, ret, bytes):
        pass

    # need connectErr handler for disconnected?
    # how to deal with "connect"-"stop connecting"-"connect"-"first connect fails"?

    def getDestination(self):
        return address.getFull(self.address, self.sockinfo)

