
# System Imports
import types

# Twisted Imports
from twisted.python import threadable

class FileDescriptor:
    """An object which can be operated on by select().
    
    This is an abstract superclass of all objects which may be notified when
    they are readable or writable; e.g. they have a file-descriptor that is
    valid to be passed to select(2).
    """
    connected = 0
    producerPaused = 0
    streamingProducer = 0
    unsent = ""
    producer = None
    disconnected = 0
    __reap = 0
    
    def connectionLost(self):
        """The connection was lost.
        
        This is called when the connection on a selectable object has been
        lost.  It will be called whether the connection was closed explicitly,
        an exception occurred in an event handler, or the other end of the
        connection closed it first.

        Clean up state here, but make sure to call back up to FileDescriptor.
        """

        self.disconnected = 1
        self.connected = 0
        if self.producer is not None:
            self.producer.stopProducing()
            self.producer = None

    def writeSomeData(self, data):
        """Write as much as possible of the given data, immediately.
        
        This is called to invoke the lower-level writing functionality, such as
        a socket's send() method, or a file's write(); this method returns an
        integer.  If positive, it is the number of bytes written; if negative,
        it indicates the connection was lost.
        """

        raise NotImplementedError("%s does not implement writeSomeData" % str(self.__class__))

    def doWrite(self):
        """Called when data is available for writing.
        """
        # Send as much data as you can.
        l = self.writeSomeData(self.unsent)
        if l < 0:
            return l
        self.unsent = self.unsent[l:]
        # If there is nothing left to send,
        if not self.unsent:
            # stop writing.
            self.stopWriting()
            # If I've got a producer who is supposed to supply me with data,
            if self.producer is not None and ((not self.streamingProducer)
                                              or self.producerPaused):
                # tell them to supply some more.
                self.producer.resumeProducing()
                self.producerPaused = 0
            elif self.__reap:
                # But if I was previously asked to let the connection die, do
                # so.
                return main.CONNECTION_DONE

    def write(self, data):
        """Reliably write some data.
        
        This adds data to be written the next time this file descriptor is
        ready for writing.  If necessary, it will wake up the I/O thread to add
        this FileDescriptor for writing, that the write will happen as soon as
        possible.
        """
        assert type(data) == types.StringType, "Data must be a string."
        if not self.connected:
            return
        if data:
            self.unsent = self.unsent + data
            if self.producer is not None:
                if len(self.unsent) > self.bufferSize:
                    self.producerPaused = 1
                    self.producer.pauseProducing()
            self.startWriting()

    def loseConnection(self):
        """Close the connection at the next available opportunity.

        Call this to cause this FileDescriptor to lose its connection; if this is in
        the main loop, it will lose its connection as soon as it's done
        flushing its write buffer; otherwise, it will wake up the main thread
        and lose the connection immediately.
        """
        if self.connected:
            self.stopReading()
            self.startWriting()
            self.__reap = 1

    def stopReading(self):
        """Stop waiting for read availability.
        
        Call this to remove this selectable from being notified when it is
        ready for reading.
        """

        main.removeReader(self)

    def stopWriting(self):
        """Stop waiting for write availability.
        
        Call this to remove this selectable from being notified when it is ready
        for writing.
        """

        main.removeWriter(self)

    def startReading(self):
        """Start waiting for read availability.
        
        Call this to remove this selectable notified whenever it is ready for
        reading.
        """

        main.addReader(self)

    def startWriting(self):
        """Start waiting for write availability.
        
        Call this to have this FileDescriptor be notified whenever it is ready for
        writing.
        """
        main.addWriter(self)

    # Producer/consumer implementation

    # first, the consumer stuff.  This requires no additional work, as
    # any object you can write to can be a consumer, really.

    producer = None
    bufferSize = 2**2**2**2

    def registerProducer(self, producer, streaming):
        """Register to receive data from a producer.

        This sets this selectable to be a consumer for a producer.  When this
        selectable runs out of data on a write() call, it will ask the producer
        to resumeProducing().  If this is a streaming producer, it will only be
        asked to resume producing if it has been previously asked to pause.
        Also, if this is a streaming producer, it will ask the producer to
        pause when the buffer has reached a certain size.

        In other words, a streaming producer is expected to produce (write to
        this consumer) data in the main IO thread of some process as the result
        of a read operation, whereas a non-streaming producer is expected to
        produce data each time resumeProducing() is called.

        FileDescriptor provides some infrastructure for producer methods.

        If this is a non-streaming producer, resumeProducing will be called
        immediately, to start the flow of data.  Otherwise it is assumed that
        the producer starts out life unpaused.

        Producers must implement the interface: """

        self.producer = producer
        self.streamingProducer = streaming
        if not streaming:
            producer.resumeProducing()

    def stopConsuming(self):
        """Stop consuming data.

        This is called when a producer has lost its connection, to tell the
        consumer to go lose its connection (and break potential circular
        references).
        """

        self.producer = None
        self.loseConnection()

    # producer interface

    def resumeProducing(self):
        """Resume producing data.
        
        This tells a producer to re-add itself to the main loop and produce
        more data for its consumer.  """

        self.startReading()

    def pauseProducing(self):
        """Pause producing data.
        
        Tells a producer that it has produced too much data to process for
        the time being, and to stop until resumeProducing() is called.  """

        self.stopReading()

    def stopProducing(self):
        """Stop producing data.
        
        This tells a producer that its consumer has died, so it must stop
        producing data for good.  """

        self.loseConnection()

    def fileno(self):
        """File Descriptor number for select().
        
        This method must be overridden or assigned in subclasses to
        indicate a valid file descriptor for the operating system.
        """
        raise NotImplementedError(str(self.__class__)+' has no fileno method')

    synchronized = ['doWrite', 'write', 'connectionLost']

threadable.synchronize(FileDescriptor)

# Sibling Imports
import main

