# TODO:
# fix connectionLost reasons (need to experiment with ReadFile/WriteFile retcodes)
# remove from proactor's handlers list

from twisted.python import log, failure
from twisted.persisted import styles
from twisted.internet import interfaces
from twisted.internet.main import CONNECTION_LOST

from win32file import AllocateReadBuffer
from pywintypes import OVERLAPPED

class IoHandle(log.Logger, styles.Ephemeral):
    """An object on which overlapped operations can be issued"""

    __implements__ = (interfaces.IProducer, interfaces.IConsumer, interfaces.ITransport)
    connected = 0
    producerPaused = 0
    streamingProducer = 0
    producer = None
    disconnecting = 0
    writebuf = None # TODO: pretty please refactor me to be a list and later to use scatter/gather IO
    offset = 0
    reading = 0
    writing = 0
    reactor = None
    readbuf = None
    outOverlapped = None
    inOverlapped = None

    def __init__(self, reactor = None):
        if not reactor:
            from twisted.internet import reactor
        self.reactor = reactor
        self.outOverlapped = OVERLAPPED()
        self.inOverlapped = OVERLAPPED()
        self.readData = win32file.AllocateReadBuffer(self.bufferSize)
        self.outOverlapped.object = "readDone"
        self.inOverlapped.object = "writeDone"

    def write(self, data):
        # this is mindnumblingly broken and leads to arbitrary-length strings
        # (as opposed to arbitrary-length lists of same size, for scatter/gather)
        self.writebuf += data
        if not self.writing:
            self.startWriting()
        if self.producer is not None:
            if len(self.writebuf) - self.offset > self.bufferSize:
                self.producerPaused = 1
                self.producer.pauseProducing()

    def readDone(self, ret, bytes):
        """read done"""
        # possible ret is ERROR_SUCCESS for success
        # ERROR_INVALID_USER_BUFFER or ERROR_NOT_ENOUGH_MEMORY for "system is fucked up"
        # ERROR_OPERATION_ABORTED if something somehow aborted the operation
        if not self.connected:
            return
        if bytes:
            self.dataReceived(self.readbuf[:bytes])
            if self.reading:
                self.startReading()
        else:
            self.connectionLost(failure.Failure(CONNECTION_LOST))

    def writeDone(self, ret, bytes):
        """write done"""
        # same ret values as readDone
        if not self.connected:
            return
        if bytes:
            self.offset += bytes
            if len(self.writebuf) == self.offset:
                self.writebuf = ""
            if self.writebuf:
                self.startWriting()
                return
            else:
                if self.producer is not None and ((not self.streamingProducer)
                                                  or self.producerPaused):
                    # tell them to supply some more.
                    self.writing = 0
                    self.producer.resumeProducing()
                    self.producerPaused = 0
                    return
                elif self.disconnecting:
                    # But if I was previously asked to let the connection die, do
                    # so.
                    self.connectionLost(failure.Failure(CONNECTION_LOST))
                    return
                self.writing = 0
        else:
            self.connectionLost(failure.Failure(CONNECTION_LOST))

    def connectionLost(self, reason):
        """extend me in a subclass and paste the rest of itamar's code there"""
        self.connected = 0
        if self.producer is not None:
            self.producer.stopProducing()
            self.producer = None

#    def _postLoseConnection(self):
#        pass

    def writeSequence(self, iovec):
        self.write("".join(iovec))

    def loseConnection(self):
        if self.connected:
            if self.writing:
                self.disconnecting = 1
            else:
                self.connectionLost(failure.Failure(CONNECTION_LOST))

    def stopReading(self):
        self.reading = 0

    def startReading(self):
        try:
            result, readbuf = win32file.ReadFile(self.fileno(), self.readbuf, self.inOverlapped)
            assert self.readbuf is readbuf
        except win32api.error, e:
            self.connectionLost(failure.Failure(CONNECTION_LOST))

    def startWriting(self):
        self.writing = 1
        size = min(len(self.writebuf) - self.offset, self.bufferSize)
        try:
            win32file.WriteFile(self.fileno(), self.writebuf[:size], self.outOverlapped)
        except win32api.error:
            self.connectionLost(failure.Failure(CONNECTION_LOST))

    # Producer/consumer implementation

    producer = None
    bufferSize = 2**2**2**2

    def registerProducer(self, producer, streaming):
        """Register to receive data from a producer.

        This sets this selectable to be a consumer for a producer.  When this
        selectable runs out of data on a write() call, it will ask the producer
        to resumeProducing(). A producer should implement the IProducer
        interface.

        IoHandle provides some infrastructure for producer methods.
        """
        if self.producer is not None:
            raise RuntimeError("Cannot register producer %s, because producer %s was never unregistered." % (producer, self.producer))
        self.producer = producer
        self.streamingProducer = streaming
        if not streaming:
            producer.resumeProducing()

    def unregisterProducer(self):
        """Stop consuming data from a producer, without disconnecting.
        """
        self.producer = None

    def stopConsuming(self):
        """Stop consuming data.

        This is called when a producer has lost its connection, to tell the
        consumer to go lose its connection (and break potential circular
        references).
        """
        self.unregisterProducer()
        self.loseConnection()

    # producer interface implementation

    def resumeProducing(self):
        if not self.reading:
            self.startReading()

    def pauseProducing(self):
        self.stopReading()

    def stopProducing(self):
        self.loseConnection()

    def fileno(self):
        """Win32 handle

        This method must be overridden or assigned in subclasses to
        indicate a valid handle for the operating system.
        Note that file.fileno() does NOT return a Win32 handle.
        """
        raise NotImplementedError(reflect.qual(self.__class__)+' has no fileno method')

