from sets import Set
import warnings, socket

from twisted.python import log, failure
from twisted.persisted import styles
from twisted.internet import main, defer

from ops import ReadFileOp, WriteFileOp
import address, error
import iocpdebug

class RWHandle(log.Logger, styles.Ephemeral):
    # TODO: use a saner data structure for buffer entries or for buffer itself, for example an instance and a queue
    # TODO: multiple pending overlapped ops. Complex and dangerous and everything else should be working first
    writebuf = None
    # if this is a temporary solution, read_op should be allowed to allocate it
    readbuf = None
    offset = 0
    writing = 0
    reading = 0
    dead = 0
    handle = None
    lconn_deferred = None
    bufferSize = 2**2**2**2
    producerPaused = 0
    streamingProducer = 0
    producer = None
    writeBufferedSize = 0 # how much we have in the write buffer
    bufferEvents = None # a dict of event string to set of handlers
    # XXX: specify read_op/write_op kwargs in a class attribute?
    read_op = ReadFileOp
    write_op = WriteFileOp
    def __init__(self):
        from twisted.internet import reactor
        self.reactor = reactor
        self.writebuf = []
        self.readbuf = self.reactor.AllocateReadBuffer(self.bufferSize)
        self.bufferEvents = {"buffer full": Set(), "buffer empty": Set()}

    def addBufferCallback(self, handler, event):
        if iocpdebug.debug:
            print "addBufferCallback(%s, %s, %s)" % (self, handler, event)
        self.bufferEvents[event].add(handler)

    def removeBufferCallback(self, handler, event):
        if iocpdebug.debug:
            print "removeBufferCallback(%s, %s, %s)" % (self, handler, event)
        self.bufferEvents[event].remove(handler)

    def callBufferHandlers(self, event, *a, **kw):
        for i in self.bufferEvents[event].copy():
            i(*a, **kw)

    def write(self, buffer, *args, **kw):
        if iocpdebug.debug:
            print "RWHandle.write(buffer of len %s, %s" % (len(buffer), kw)
            print "    len(self.writebuf) %s, self.offset %s, self.writing %s" % \
            (len(self.writebuf), self.offset, self.writing)
        if not self.dead:
            self.writebuf.append((buffer, args, kw))
            self.writeBufferedSize += len(buffer)
            if self.writeBufferedSize >= self.bufferSize: # what's the proper semantics for this?
                self.callBufferHandlers(event = "buffer full")
            if not self.writing:
                self.writing = 1
                self.startWriting()

    # XXX: this is actually broken -- UDP has to provide its own writeSequence
    def writeSequence(self, iovec, *args, **kw):
        for i in iovec:
            self.write(i, *args, **kw)

    def startWriting(self):
        b = buffer(self.writebuf[0][0], self.offset)
        op = self.write_op()
        op.initiateOp(self.handle, b, *self.writebuf[0][1], **self.writebuf[0][2])
        op.addCallback(self.writeDone)
        op.addErrback(self.writeErr)

    def writeDone(self, bytes):
        self.offset += bytes
        self.writeBufferedSize -= bytes
        if self.offset == len(self.writebuf[0][0]):
            del self.writebuf[0]
            self.offset = 0
        if self.writebuf == []:
            self.writing = 0
            self.callBufferHandlers(event = "buffer empty")
        else:
            self.startWriting()

    def startReading(self):
        if not self.reading:
            self.reading = 1
            op = self.read_op()
            print "initiating op", self.handle
            op.initiateOp(self.handle, self.readbuf)
            op.addCallback(self.readDone)
            op.addErrback(self.readErr)

    def readDone(self, (bytes, kw)):
        # XXX: got to pass a buffer to dataReceived to avoid copying, but most of the stuff expects that
        # to support str methods. Perhaps write a perverse C extension for this, but copying IS necessary
        # if protocol wants to store this string. I wish this was C++! No, wait, I don't.
        if iocpdebug.debug:
            print "RWHandle.readDone(%s, (%s, %s))" % (self, bytes, kw)
            print "    self.reading is", self.reading
        self.dataReceived(self.readbuf[:bytes], **kw)
        if self.reading:
            self.startReading()

    def dataReceived(self, data, **kw):
        raise NotImplementedError
    
    def readErr(self, err):
        if iocpdebug.debug:
            print "RWHandle.readErr(%s, %s)" % (self, err)
        if isinstance(err, error.NonFatalException):
            self.startReading() # delay or just fail?
        else:
            self.stopWorking(err)

    def writeErr(self, err):
        if iocpdebug.debug:
            print "RWHandle.writeErr(%s, %s)" % (self, err)
            import traceback
            traceback.print_stack()
        if isinstance(err, error.NonFatalException):
            self.startWriting() # delay or just fail?
        else:
            self.stopWorking(err)

    def stopWorking(self, err):
        if not self.dead:
            self.dead = 1
            self.stopReading()
            self.stopWriting()
            del self.handle
            self.handleDead(err)

    def handleDead(self, err):
        raise NotImplementedError

    def stopReading(self):
        self.reading = 0

    def stopWriting(self):
        self.writing = 0

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
        """Stop consuming data from a producer, without disconnecting.
        """
        self.removeBufferCallback(self.stfuProducer, "buffer full")
        self.removeBufferCallback(self.milkProducer, "buffer empty")
        self.producer = None

    def stopConsuming(self):
        """Stop consuming data.

        This is called when a producer has lost its connection, to tell the
        consumer to go lose its connection (and break potential circular
        references).
        """
        self.unregisterProducer()
        self.loseConnection() # XXX: bad assumption for this class, but oh well

    # producer interface implementation

    def resumeProducing(self):
        self.startReading()

    def pauseProducing(self):
        self.stopReading()

    def stopProducing(self):
        self.loseConnection() # XXX: bad assumption for this class, but oh well

    def loseConnection(self):
        raise NotImplementedError

    def logPrefix(self):
        return self.logstr

class ConnectedSocket(RWHandle):
#    read_op = WSARecvOp
#    write_op = WSASendOp
    logstr = None
    repstr = None
    disconnecting = 0

    def __init__(self, sock, protocol, sf):
        RWHandle.__init__(self)
        self.socket = sock
        self.handle = sock.fileno()
        self.protocol = protocol
        self.sf = sf

    def __repr__(self):
        """A string representation of this connection.
        """
        return self.repstr

    def getHost(self):
        return address.getFull(self.socket.getsockname(), self.sf.af, self.sf.type, self.sf.proto)

    def getPeer(self):
        return address.getFull(self.socket.getpeername(), self.sf.af, self.sf.type, self.sf.proto)

    def dataReceived(self, data, **kw):
        self.protocol.dataReceived(data)

    def handleDead(self, reason):
        if iocpdebug.debug:
            print "ConnectedSocket.handleDead(%s, %s)" % (self, reason)
        protocol = self.protocol
        del self.protocol
        self.socket.close()
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
        if iocpdebug.debug:
            print "ConnectedSocket.loseConnection(%s)" % (self,)
        def callback():
            self.removeBufferCallback(callback, "buffer empty")
            try:
                self.socket.shutdown(2)
            except socket.error:
                pass
            self.stopWorking(failure.Failure(main.CONNECTION_DONE))
            self.disconnecting = 0
            self.lconn_deferred.callback(None)
            del self.lconn_deferred
        self.stopReading()
        if self.writing:
            self.lconn_deferred = defer.Deferred()
            self.addBufferCallback(callback, "buffer empty")
            self.disconnecting = 1
            return self.lconn_deferred
        else:
            self.stopWorking(failure.Failure(main.CONNECTION_DONE))
            return None

