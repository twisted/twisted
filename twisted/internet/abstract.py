
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


# System Imports
import types, string

# Twisted Imports
from twisted.python import log

# Sibling Imports
import interfaces


class FileDescriptor(log.Logger):
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
    disconnecting = 0

    __implements__ = (interfaces.IProducer,)

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
            elif self.disconnecting:
                # But if I was previously asked to let the connection die, do
                # so.
                return main.CONNECTION_DONE

    def write(self, data):
        """Reliably write some data.

        If there is no buffered data this tries to write this data immediately,
        otherwise this adds data to be written the next time this file descriptor is
        ready for writing.
        """
        assert type(data) == types.StringType, "Data must be a string."
        if not self.connected:
            return
        if data:
            if not self.unsent:
                l = self.writeSomeData(data)
                if l == len(data):
                    # all data was sent, our work here is done
                    return
                elif l > 0:
                    # some data was sent
                    self.unsent = data[l:]
                else:
                    # either no data was sent, or we were disconnected.
                    # if we were disconnected we still continue, so that
                    # the event loop can figure it out later on.
                    self.unsent = data
            else:
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
            self.disconnecting = 1

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
        to resumeProducing(). A producer should implement the IProducer
        interface.

        FileDescriptor provides some infrastructure for producer methods.
        """

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
        self.startReading()

    def pauseProducing(self):
        self.stopReading()

    def stopProducing(self):
        self.loseConnection()


    def fileno(self):
        """File Descriptor number for select().

        This method must be overridden or assigned in subclasses to
        indicate a valid file descriptor for the operating system.
        """
        raise NotImplementedError(str(self.__class__)+' has no fileno method')



def isIPAddress(addr):
    parts = string.split(addr, '.')
    if len(parts) == 4:
        try:
            for part in map(int, parts):
                if not (0<=part<256):
                    break
            else:
                return 1
        except ValueError:
                pass
    return 0

# Sibling Imports
import main
