class RWHandle(log.logger, styles.Ephemeral):
    # XXX: use a saner data structure for buffer entries or for buffer itself, for example an instance and a queue
    writebuf = None
    offset = 0
    writing = 0
    bufferSize = 2**2**2**2
    # XXX: specify read_op/write_op kwargs in a class attribute?
    read_op = ReadFileOp
    write_op = WriteFileOp
    # XXX: we don't care about producer/consumer crap, let itamar and other smarties fix the stuff first
    def __init__(self):
        self.writebuf = []
        self.readbuf = AllocateReadBuffer(self.bufferSize)

    def write(self, buffer, **kw):
        self.writebuf.append((buffer, kw))
        if not self.writing:
            self.writing = 1
            self.startWriting()

    def startWriting(self):
        b = buffer(self.writebuf[0][0], self.offset)
        op = self.write_op(self.handle, b, **self.writebuf[0][1])
        # XXX: errback/callback order! this should do callback if no error and do errback if there is an error
        # without propagating return value to callback. What are the semantics on that?
        op.addCallback(self.writeDone)
        op.addErrback(self.writeErr)

    def writeDone(self, bytes):
        # XXX: bytes == 0 should be checked by OverlappedOp, as it is an error condition
        self.offset += bytes
        if self.offset == len(self.writebuf[0]):
            del self.writebuf[0]
        if self.writebuf == []:
            self.writing = 0
        else:
            self.startWriting()

    def writeErr(self, err):
        raise NotImplementedError

    # called at start and never again? depends on future consumer thing
    def startReading(self):
        op = self.read_op(self.handle, self.readbuf, {})
        op.addCallback(self.readDone)
        op.addErrback(self.readErr)

    def readDone(self, (bytes, kw)):
        # XXX: got to pass a buffer to dataReceived to avoid copying, but most of the stuff expects that
        # to support str methods. Perhaps write a perverse C extension for this, but copying IS necessary
        # if protocol wants to store this string. I wish this was C++! No, wait, I don't.
        self.dataReceived(self.readbuf[:bytes], **kw)
        self.startReading()

    def dataReceived(self, data, **kw):
        raise NotImplementedError

    def readErr(self, err):
        raise NotImplementedError

# this is a handle with special read/write ops and error handling, Protocol dispatch and connection loss
class Socket(RWHandle):
    read_op = WSARecvOp
    write_op = WSASendOp

    def __init__(self, skt, protocol):
        self.socket = skt
        self.handle = skt.fileno()
        self.protocol = protocol

class ConnectedSocket(Socket):
    def dataReceived(self, data, **kw):
        self.protocol.dataReceived(data)

    def writeErr(self, err):
        # XXX: depending on whether it was cancelled or
        # a socket fuckup occurred, what should we do?
        self.connectionLost(err)

    def readErr(self, err):
        self.connectionLost(err)

    def connectionLost(self, err):
        # TODO: copy and paste to do the right thing
        self.socket.shutdown(2) # close the socket too?
        self.protocol.connectionLost(err)

    def loseConnection(self):
        # TODO: groan, "write remaining data" semantics
        # where should that stuff be?
        pass

# TODO: devise a socket family specific initialization method
class AbstractSocketPort:
    addressFamily = None
    socketType = None
    def __init__(self, address, factory, backlog, **kw):
        self.address = address
        self.factory = factory
        self.kw = kw

    def startListening(self):
        skt = socket(self.addressFamily, self.socketType)
        skt.bind(self.address)

class ListenSocketPort(SocketPort):
    transport = ConnectedSocket
    accept_op = AcceptExOp
        skt.listen(self.backlog)
        self.startAccepting

