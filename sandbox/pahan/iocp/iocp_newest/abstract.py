from sets import Set
import warnings

from twisted.internet import interfaces, defer, main
from twisted.persisted import styles
from twisted.python import log, failure

from ops import ReadFileOp, WriteFileOp
import address

class ConnectedSocket(log.Logger, styles.Ephemeral):
    __implements__ = interfaces.ITransport, interfaces.IProducer, interfaces.IConsumer
    events = ["write", "loseConnection", "writeDone", "writeErr", "readDone", "readErr"]
    bufferSize = 2**2**2**2
    producer = None
    writing = 0
    reading = 0
    disconnecting = 0 # groan, stupid LineReceiver and LineOnlyReceiver want to see this in a transport
    def __init__(self, socket, protocol, sockfactory):
        self.state = "connected"
        from twisted.internet import reactor
        self.socket = socket
        self.protocol = protocol
        self.sf = sockfactory
        self.writebuf = []
        self.readbuf = reactor.AllocateReadBuffer(self.bufferSize)
        self.reactor = reactor
        self.bufferEvents = {"buffer full": Set(), "buffer empty": Set()}
        self.offset = 0
        self.writeBufferedSize = 0
        self.read_op = ReadFileOp(self)
        self.write_op = WriteFileOp(self) # XXX: these two should be specified like before, with a class field

    def addBufferCallback(self, handler, event):
        self.bufferEvents[event].add(handler)

    def removeBufferCallback(self, handler, event):
        self.bufferEvents[event].remove(handler)

    def callBufferHandlers(self, event, *a, **kw):
        for i in self.bufferEvents[event].copy():
            i(*a, **kw)

    def handle_connected_write(self, data):
        if self.writebuf and len(self.writebuf[-1]) < self.bufferSize: # mmmhhh silly heuristics
            self.writebuf[-1] += data
        else:
            self.writebuf.append(data)
        self.writeBufferedSize += len(data)
        if self.writeBufferedSize >= self.bufferSize:
            self.callBufferHandlers(event = "buffer full")
        if not self.writing:
            self.startWriting()

    handle_disconnecting_write = handle_connected_write

    def writeSequence(self, iovec):
        self.write("".join(iovec))

    def _cbDisconnecting(self):
        if self.producer:
            return
        self.removeBufferCallback(self._cbDisconnecting, "buffer empty")
        self.connectionLost(failure.Failure(main.CONNECTION_DONE))

    def handle_connected_loseConnection(self, err):
        self.stopReading()
        if self.writing:
            self.addBufferCallback(self._cbDisconnecting, "buffer empty")
            self.state = "disconnecting"
            self.disconnecting = 1
        else:
            self.connectionLost(err)
            return None

    def connectionLost(self, reason):
        self.state = "disconnected"
        self.disconnecting = 0
        protocol = self.protocol
        del self.protocol
        # XXX: perhaps the following needs to be around to avoid resetting the connection ungracefully
#        try:
#            self.socket.shutdown(2)
#        except socket.error:
#            pass
        self.socket.close() # this should call closesocket() and kill it dead!
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

    def startReading(self):
        self.reading = 1
        try:
            self.read_op.initiateOp(self.socket.fileno(), self.readbuf)
        except Exception:
            log.err()
            self.loseConnection()

    def stopReading(self):
        self.reading = 0

    def handle_connected_readDone(self, bytes):
        self.protocol.dataReceived(self.readbuf[:bytes])
        if self.reading:
            self.startReading()

    def handle_disconnecting_readDone(self, bytes):
        pass # a leftover read op from before we began disconnecting

    def handle_connected_readErr(self, ret, bytes):
        self.loseConnection(failure.Failure(main.CONNECTION_DONE))

    handle_disconnecting_readErr = handle_connected_readErr
    
    def handle_disconnected_readErr(self, ret, bytes):
        pass # no kicking the dead horse

    def startWriting(self):
        self.writing = 1
        b = buffer(self.writebuf[0], self.offset)
        try:
            self.write_op.initiateOp(self.socket.fileno(), b)
        except Exception:
            log.err()
            self.loseConnection()

    def stopWriting(self):
        self.writing = 0

    def handle_connected_writeDone(self, bytes):
        self.offset += bytes
        self.writeBufferedSize -= bytes
        if self.offset == len(self.writebuf[0]):
            del self.writebuf[0]
            self.offset = 0
        if self.writebuf == []:
            self.writing = 0
            self.callBufferHandlers(event = "buffer empty")
        else:
            self.startWriting()

    handle_disconnecting_writeDone = handle_connected_writeDone

    def handle_connected_writeErr(self, ret, bytes):
        self.loseConnection(failure.Failure(main.CONNECTION_DONE))

    handle_disconnecting_writeErr = handle_connected_writeErr
    
    def handle_disconnected_writeErr(self, ret, bytes):
        pass # no kicking the dead horse

    # consumer interface implementation

    def registerProducer(self, producer, streaming):
        if self.producer is not None:
            raise RuntimeError("Cannot register producer %s, because producer %s was never unregistered." % (producer, self.producer))
        self.producer = producer
        self.streamingProducer = streaming
        self.addBufferCallback(self.milkProducer, "buffer empty")
        self.addBufferCallback(self.stfuProducer, "buffer full")
        if not streaming:
            producer.resumeProducing()

    def milkProducer(self):
        if not self.streamingProducer or self.producerPaused:
            self.producer.resumeProducing()
            self.producerPaused = 0

    def stfuProducer(self):
        self.producerPaused = 1
        self.producer.pauseProducing()
        
    def unregisterProducer(self):
        self.removeBufferCallback(self.stfuProducer, "buffer full")
        self.removeBufferCallback(self.milkProducer, "buffer empty")
        self.producer = None

    def stopConsuming(self):
        self.unregisterProducer()
        self.loseConnection()

    # producer interface implementation

    def resumeProducing(self):
        self.startReading()

    def pauseProducing(self):
        self.stopReading()

    def stopProducing(self):
        self.loseConnection()

    def getHost(self):
        return address.getFull(self.socket.getsockname(), self.sf.sockinfo)

    def getPeer(self):
        return address.getFull(self.socket.getpeername(), self.sf.sockinfo)

    def __repr__(self):
        return self.repstr

    def logPrefix(self):
        return self.logstr

def makeHandleGetter(name):
    def helpful(self):
        return getattr(self, "handle_%s_%s" % (self.state, name))
    return helpful

for i in ConnectedSocket.events:
    setattr(ConnectedSocket, i, property(makeHandleGetter(i)))

