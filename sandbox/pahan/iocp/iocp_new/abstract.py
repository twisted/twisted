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
        # TODO: call connectionLost or some such. Restart if cancelled?
        pass

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
        # TODO: call connectionLost or some such. Restart if cancelled?
        pass

class Port:
    def __init__(self
    def startListening(self):
        pass

    def stopListening(self):
        pass

    def getHost(self):
        pass

