from twisted.internet import tcp # and confusion begins
import abstract # TODO: change me to fully-qualified name

class Connection(abstract.IoHandle):
    """I am the superclass of all socket-based FileDescriptors.

    This is an abstract superclass of all objects which represent a TCP/IP
    connection based socket.
    """

    __implements__ = abstract.IoHandle.__implements__, interfaces.ITCPTransport

    TLS = 0

    def __init__(self, skt, protocol, reactor=None):
        abstract.IoHandle.__init__(self, reactor=reactor)
        self.socket = skt
#        self.socket.setblocking(0)
#        self.fileno = skt.fileno
        self.protocol = protocol

"""
    if SSL:
        __implements__ = __implements__ + (interfaces.ITLSTransport,)

        def startTLS(self, ctx):
            assert not self.TLS
            self.stopReading()
            self.stopWriting()
            self._startTLS()
            self.socket = SSL.Connection(ctx.getContext(), self.socket)
            self.fileno = self.socket.fileno
            self.startReading()

        def _startTLS(self):
            self.TLS = 1
            class TLSConnection(_TLSMixin, self.__class__):
                pass
            self.__class__ = TLSConnection
"""

    def doRead(self):
        """Calls self.protocol.dataReceived with all available data.

        This reads up to self.bufferSize bytes of data from its socket, then
        calls self.dataReceived(data) to process it.  If the connection is not
        lost through an error in the physical recv(), this function will return
        the result of the dataReceived call.
        """
        try:
            data = self.socket.recv(self.bufferSize)
        except socket.error, se:
            if se.args[0] == EWOULDBLOCK:
                return
            else:
                return main.CONNECTION_LOST
        except SSL.SysCallError, (retval, desc):
            # Yes, SSL might be None, but self.socket.recv() can *only*
            # raise socket.error, if anything else is raised, it must be an
            # SSL socket, and so SSL can't be None. (That's my story, I'm
            # stickin' to it)
            if retval == -1 and desc == 'Unexpected EOF':
                return main.CONNECTION_DONE
            raise
        if not data:
            return main.CONNECTION_DONE
        return self.protocol.dataReceived(data)

    def writeSomeData(self, data):
        """Connection.writeSomeData(data) -> #of bytes written | CONNECTION_LOST
        This writes as much data as possible to the socket and returns either
        the number of bytes read (which is positive) or a connection error code
        (which is negative)
        """
        try:
            return self.socket.send(data)
        except socket.error, se:
            if se.args[0] == EINTR:
                return self.writeSomeData(data)
            elif se.args[0] == EWOULDBLOCK:
                return 0
            else:
                return main.CONNECTION_LOST

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
        """See abstract.FileDescriptor.connectionLost().
        """
        abstract.FileDescriptor.connectionLost(self, reason)
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

class Connector(tcp.Connector):
    def _makeTransport(self):
        return Client(self.host, self.port, self.bindAddress, self, self.reactor)

