import abstract # TODO: change me to fully-qualified name

from win32file import AcceptEx, GetAcceptExSockaddrs, SO_UPDATE_ACCEPT_CONTEXT
from pywintypes import OVERLAPPED

import operator, socket, struct
import winerror

class Connection(abstract.IoHandle):
    """I am the superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.
    """

    __implements__ = abstract.IoHandle.__implements__, interfaces.ITCPTransport

    def __init__(self, skt, protocol, reactor = None):
        abstract.IoHandle.__init__(self, reactor = reactor)
        self.socket = skt
        self.fileno = skt.fileno
        self.reactor.registerFile(self.fileno(), self)
        self.protocol = protocol

    def _closeSocket(self):
        """Called to close our socket."""
        # This used to close() the socket, but that doesn't *really* close if
        # there's another reference to it in the TCP/IP stack, e.g. if it was
        # was inherited by a subprocess. And we really do want to close the
        # connection. So we use shutdown() instead.
        try:
            self.socket.shutdown(2)
        except socket.error:
            pass

    def connectionLost(self, reason):
        """See abstract.IoHandle.connectionLost"""
        abstract.IoHandle.connectionLost(self, reason)
        self._closeSocket()
        protocol = self.protocol
        del self.protocol
        del self.socket
        del self.fileno
        try:
            protocol.connectionLost(reason)
        except TypeError, e:
            # while this may break, it will only break on deprecated code
            # as opposed to other approaches that might've broken on
            # code that uses the new API (e.g. inspect).
            if e.args and e.args[0] == "connectionLost() takes exactly 1 argument (2 given)":
                warnings.warn("Protocol %s's connectionLost should accept a reason argument" % protocol,
                              category=DeprecationWarning, stacklevel=2)
                protocol.connectionLost()
            else:
                raise

    logstr = "Uninitialized"

    def logPrefix(self):
        """Return the prefix to log with when I own the logging thread.
        """
        return self.logstr

    def getTcpNoDelay(self):
        return operator.truth(self.socket.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY))

    def setTcpNoDelay(self, enabled):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, enabled)

    def getTcpKeepAlive(self):
        return operator.truth(self.socket.getsockopt(socket.SOL_SOCKET,
                                                     socket.SO_KEEPALIVE))

    def setTcpKeepAlive(self, enabled):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, enabled)

class Server(Connection):
    """Serverside socket-stream connection class.

    I am a serverside network connection transport; a socket which came from an
    accept() on a server.
    """

    def __init__(self, sock, protocol, client, server, sessionno):
        """Server(sock, protocol, client, server, sessionno)

        Initialize me with a socket, a protocol, a descriptor for my peer (a
        tuple of host, port describing the other end of the connection), an
        instance of Port, and a session number.
        """
        Connection.__init__(self, sock, protocol)
        self.server = server
        self.client = client
        self.sessionno = sessionno
        self.hostname = client[0]
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno, self.hostname)
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, self.sessionno, self.server.port)
        self.startReading()
        self.connected = 1

    def __repr__(self):
        """A string representation of this connection.
        """
        return self.repstr

    def startTLS(self, ctx, server=1):
        holder = Connection.startTLS(self, ctx)
        if server:
            self.socket.set_accept_state()
        else:
            self.socket.set_connect_state()
        return holder

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the servers address.
        """
        return ('INET',)+self.socket.getsockname()

    def getPeer(self):
        """
        Returns a tuple of ('INET', hostname, port), indicating the connected
        client's address.
        """
        return ('INET',)+self.client

class Port(abstract.IoHandle):
    """I am a TCP server port, listening for connections.

    When a connection is accepted, I will call my factory's buildProtocol with
    the incoming connection as an argument, according to the specification
    described in twisted.internet.interfaces.IProtocolFactory.

    If you wish to change the sort of transport that will be used, my
    `transport' attribute will be called with the signature expected for
    Server.__init__, so it can be replaced.
    """
    addressFamily = socket.AF_INET
    socketType = socket.SOCK_STREAM

    transport = Server
    sessionno = 0
    interface = ''
    backlog = 5
    acOverlapped = None
    acceptSocket = None
    acceptbuf = None

    def __init__(self, port, factory, backlog=5, interface='', reactor=None):
        """Initialize with a numeric port to listen on."""
        abstract.IoHandle.__init__(self, reactor = reactor)
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface
        self.acOverlapped = OVERLAPPED()
        self.acOverlapped.object = "acceptDone"
        self.acceptbuf = AllocateReadBuffer(64) # XXX: AF_INET specific, see AcceptEx documentation in win32all

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, self.port)

    def createInternetSocket(self):
        s = socket.socket(self.addressFamily, self.socketType)
        return s

    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        log.msg("%s starting on %s"%(self.factory.__class__, self.port))
        try:
            skt = self.createInternetSocket()
            skt.bind((self.interface, self.port))
        except socket.error, le:
            raise CannotListenError, (self.interface, self.port, le)
        self.factory.doStart()
        skt.listen(self.backlog)
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno
        self.reactor.registerFile(self.fileno(), self)
        self.startAccepting()

    def startAccepting(self):
        self.acceptSocket = self.createInternetSocket()
        AcceptEx(self.socket, self.acceptSocket, self.acceptbuf, self.acOverlapped)

    def acceptDone(self, ret, bytes):
        """Called when my socket is ready for reading.

        This accepts a connection and calls self.protocol() to handle the
        wire-level protocol.
        """
        if not self.connected or ret == winerror.ERROR_OPERATION_ABORTED:
            return
        try:
            skt = self.acceptSocket
            del self.acceptSocket

            # make new socket inherit properties from the port's socket
            skt.setsockopt(socket.SOL_SOCKET, SO_UPDATE_ACCEPT_CONTEXT, struct.pack("I", self.fileno()))

            # get new socket's address
            family, localaddr, addr = GetAcceptExSockaddrs(self.socket, self.acceptbuf)

            # build the new protocol
            protocol = self.factory.buildProtocol(addr)
            if protocol is None:
                skt.close()
            else:
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(skt, protocol, addr, self, s)
                protocol.makeConnection(transport, self)
        except:
            log.deferr()
        
        self.startAccepting()

    def loseConnection(self, connDone=failure.Failure(main.CONNECTION_DONE)):
        """Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        It returns a deferred which will fire successfully when the
        port is actually closed.
        """
        if self.connected:
            self.deferred = defer.Deferred()
            self.reactor.callLater(0, self.connectionLost, connDone)
            return self.deferred

    stopListening = loseConnection

    def connectionLost(self, reason):
        """Cleans up my socket.
        """
        log.msg('(Port %r Closed)' % self.port)
        base.BasePort.connectionLost(self, reason)
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.fileno
        self.factory.doStop()
        self.deferred.callback(None)
        del self.deferred

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the server's address.
        """
        return ('INET',)+self.socket.getsockname()

class Connector(base.BaseConnector):
    def __init__(self, host, port, factory, timeout, bindAddress, reactor=None):
        self.host = host
        if isinstance(port, types.StringTypes):
            try:
                port = socket.getservbyname(port, 'tcp')
            except socket.error, e:
                raise error.ServiceNameUnknownError(string=str(e))
        self.port = port
        self.bindAddress = bindAddress
        base.BaseConnector.__init__(self, factory, timeout, reactor)

    def _makeTransport(self):
        return Client(self.host, self.port, self.bindAddress, self, self.reactor)

    def getDestination(self):
        return ('INET', self.host, self.port)

