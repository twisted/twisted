from sets import Set
import warnings
import socket

from twisted.python import log, reflect
from twisted.persisted import styles
from twisted.internet import defer, main

# sibling imports, change to fully-qualified at release (or not, circular imports :(
from ops import ReadFileOp, WriteFileOp, WSARecvOp, WSASendOp, AcceptExOp
from error import GenCannotListenError

class RWHandle(log.Logger, styles.Ephemeral):
    # XXX: use a saner data structure for buffer entries or for buffer itself, for example an instance and a queue
    writebuf = None
    # if this is a temporary solution, read_op should be allowed to allocate it
    readbuf = None
    offset = 0
    writing = 0
    reading = 0
    bufferSize = 2**2**2**2
    writeBufferedSize = 0 # how much we have in the write buffer
    bufferhandlers = None
    # XXX: specify read_op/write_op kwargs in a class attribute?
    read_op = ReadFileOp
    write_op = WriteFileOp
    # XXX: we don't care about producer/consumer crap, let itamar and other smarties fix the stuff first
    def __init__(self):
        from twisted.internet import reactor
        self.reactor = reactor
        self.writebuf = []
        self.readbuf = self.reactor.AllocateReadBuffer(self.bufferSize)
        self.bufferhandlers = Set()

    def addBufferCallback(self, handler):
        self.bufferhandlers.add(handler)

    def removeBufferCallback(self, handler):
        self.bufferhandlers.remove(handler)

    def callBufferHandlers(self, *a, **kw):
        for i in self.bufferhandlers:
            i(*a, **kw)

    def write(self, buffer, **kw):
        self.writebuf.append((buffer, kw))
        self.writeBufferedSize += len(buffer)
        if self.writeBufferedSize >= self.bufferSize: # what's the proper semantics for this?
            self.callBufferHandlers(type = "buffer full")
        if not self.writing:
            self.writing = 1
            self.startWriting()

    def startWriting(self):
        b = buffer(self.writebuf[0][0], self.offset)
        op = self.write_op()
        # XXX: errback/callback order! this should do callback if no error and do errback if there is an error
        # without propagating return value to callback. What are the semantics on that?
        op.addCallback(self.writeDone)
        op.addErrback(self.writeErr)
        op.initiateOp(self.handle, b, **self.writebuf[0][1])

    def writeDone(self, bytes):
        # XXX: bytes == 0 should be checked by OverlappedOp, as it is an error condition
        self.offset += bytes
        self.writeBufferedSize -= bytes
        if self.offset == len(self.writebuf[0]):
            del self.writebuf[0]
        if self.writebuf == []:
            self.writing = 0
            self.callBufferHandlers(type = "buffer empty")
        else:
            self.startWriting()

    def writeErr(self, err):
        raise NotImplementedError

    # called at start and never again? depends on future consumer thing
    def startReading(self):
        op = self.read_op()
        op.addCallback(self.readDone)
        op.addErrback(self.readErr)
        op.initiateOp(self.handle, self.readbuf, {})

    def readDone(self, (bytes, kw)):
        # XXX: got to pass a buffer to dataReceived to avoid copying, but most of the stuff expects that
        # to support str methods. Perhaps write a perverse C extension for this, but copying IS necessary
        # if protocol wants to store this string. I wish this was C++! No, wait, I don't.
        self.dataReceived(self.readbuf[:bytes], **kw)
        if self.reading:
            self.startReading()

    def dataReceived(self, data, **kw):
        raise NotImplementedError

    def readErr(self, err):
        raise NotImplementedError

    def stopReading(self):
        self.reading = 0

# this is a handle with special read/write ops and error handling, Protocol dispatch and connection loss
class Socket(RWHandle):
    read_op = WSARecvOp
    write_op = WSASendOp

    def __init__(self, sock, protocol, client, server, sessionno):
        RWHandle.__init__(self)
        self.socket = sock
        self.handle = sock.fileno()
        self.protocol = protocol
        self.client = client
        self.server = server
        self.sessionno = sessionno
        # XXX: Twisted needs a "socket address" class
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno, self.client)
        # same with self.server.port
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, self.sessionno, self.server.address)
        self.startReading()
#        self.connected = 1

    def __repr__(self):
        """A string representation of this connection.
        """
        return self.repstr

    def getHost(self):
        return (self.server.afPrefix,)+self.socket.getsockname()

    def getPeer(self):
        return (self.server.afPrefix,)+self.client

    def dataReceived(self, data, **kw):
        self.protocol.dataReceived(data)

    def writeErr(self, err):
        # XXX: depending on whether it was cancelled or
        # a socket fuckup occurred, what should we do?
        self.connectionLost(err)

    def readErr(self, err):
        self.connectionLost(err)

    def connectionLost(self, reason):
        try:
            self.socket.shutdown(2)
        except socket.error:
            pass
        protocol = self.protocol
        del self.protocol
        del self.socket
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

    def loseConnection(self):
        def callback(self, v):
            if v == "buffer empty":
                self.connectionLost(main.CONNECTION_DONE)
                self.lconn_deferred.callback(main.CONNECTION_DONE)
                del self.lcon_deferred
                self.removeBufferCallback(callback)
        self.stopReading()
        self.lconn_deferred = defer.Deferred()
        if self.writing:
            self.addBufferCallback(callback)
        return self.lcon_deferred

class SocketPort:
    transport = Socket
    accept_op = AcceptExOp
    afPrefix = None
    addressFamily = None
    socketType = None
    accepting = 0
    sessionno = 0
    address = None
    factory = None
    backlog = None
    def __init__(self, address, factory, backlog, **kw):
        self.address = address
        self.factory = factory
        self.backlog = backlog
        self.kw = kw

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, self.address)

    def startListening(self):
        log.msg("%s starting on %s"%(self.factory.__class__, self.address))
        try:
            skt = socket.socket(self.addressFamily, self.socketType)
            skt.bind(self.address)
        except socket.error, le:
            raise GenCannotListenError, (self.address, le)
        self.factory.doStart()
        skt.listen(self.backlog)
        self.accepting = 1
        self.socket = skt
        self.handle = skt.fileno()
        self.startAccepting()

    def startAccepting(self):
        op = self.accept_op()
        op.addCallback(self.acceptDone)
        op.addErrback(self.acceptErr)
        op.initiateOp(self.handle)

    def acceptDone(self, (sock, addr)):
        if self.accepting:
            protocol = self.factory.buildProtocol(addr)
            if protocol is None:
                sock.close()
            else:
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(sock, protocol, addr, self, s)
                protocol.makeConnection(transport)
            self.startAccepting()

    def acceptErr(self, err):
        log.deferr(err)

    def stopListening(self):
        log.msg('(Port %r Closed)' % self.address)
        self.accepting = 0
        self.reactor.CancelIo(self.socket.fileno())
        self.socket.close()
        del self.socket
        self.factory.doStop()

    loseConnection = stopListening

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the server's address.
        """
        return (self.afPrefix,)+self.socket.getsockname()

