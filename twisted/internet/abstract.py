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

"""Support for generic select()able objects.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import types, string

# Twisted Imports
from twisted.python import log, reflect
from twisted.persisted import styles

# Sibling Imports
import interfaces

class FileDescriptor(log.Logger, styles.Ephemeral):
    """An object which can be operated on by select().

    This is an abstract superclass of all objects which may be notified when
    they are readable or writable; e.g. they have a file-descriptor that is
    valid to be passed to select(2).
    """
    connected = 0
    producerPaused = 0
    streamingProducer = 0
    producer = None
    disconnected = 0
    disconnecting = 0
    dataBuffer = ""
    offset = 0

    __implements__ = (interfaces.IProducer, interfaces.IReadWriteDescriptor,
                      interfaces.IConsumer, interfaces.ITransport)

    def __init__(self, reactor=None):
        if not reactor:
            from twisted.internet import reactor
        self.reactor = reactor

    def connectionLost(self, reason):
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

        raise NotImplementedError("%s does not implement writeSomeData" %
                                  reflect.qual(self.__class__))

    def doWrite(self):
        """Called when data is available for writing.

        A result that is true (which will be a negative number) implies the
        connection was lost. A false result implies the connection is still
        there; a result of 0 implies no write was done, and a result of None
        indicates that a write was done.
        """
        # Send as much data as you can.
        if self.offset:
            l = self.writeSomeData(buffer(self.dataBuffer, self.offset))
        else:
            l = self.writeSomeData(self.dataBuffer)
        if l < 0 or isinstance(l, Exception):
            return l
        if l == 0 and self.dataBuffer:
            result = 0
        else:
            result = None
        self.offset += l
        # If there is nothing left to send,
        if self.offset == len(self.dataBuffer):
            self.dataBuffer = ""
            self.offset = 0
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
                return self._postLoseConnection()
        return result

    def _postLoseConnection(self):
        """Called after a loseConnection(), when all data has been written.

        Whatever this returns is then returned by doWrite.
        """
        # default implementation, telling reactor we're finished
        return main.CONNECTION_DONE

    def write(self, data):
        """Reliably write some data.

        If there is no buffered data this tries to write this data immediately,
        otherwise this adds data to be written the next time this file descriptor is
        ready for writing.
        """
        assert isinstance(data, str), "Data must be a string."
        if not self.connected:
            return
        if data:
            if (not self.dataBuffer) and (self.producer is None):
                l = self.writeSomeData(data)
                if l == len(data):
                    # all data was sent, our work here is done
                    return
                elif not isinstance(l, Exception) and l > 0:
                    # some data was sent
                    self.dataBuffer = data
                    self.offset = l
                else:
                    # either no data was sent, or we were disconnected.
                    # if we were disconnected we still continue, so that
                    # the event loop can figure it out later on.
                    self.dataBuffer = data
            else:
                self.dataBuffer = self.dataBuffer + data
            if self.producer is not None:
                if len(self.dataBuffer) > self.bufferSize:
                    self.producerPaused = 1
                    self.producer.pauseProducing()
            self.startWriting()

    def writeSequence(self, iovec):
        self.write("".join(iovec))

    def loseConnection(self):
        """Close the connection at the next available opportunity.

        Call this to cause this FileDescriptor to lose its connection; if this is in
        the main loop, it will lose its connection as soon as it's done
        flushing its write buffer; otherwise, it will wake up the main thread
        and lose the connection immediately.

        If you have a producer registered, the connection won't be closed until the
        producer is finished. Therefore, make sure you unregister your producer
        when it's finished, or the connection will never close.
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
        self.reactor.removeReader(self)

    def stopWriting(self):
        """Stop waiting for write availability.

        Call this to remove this selectable from being notified when it is ready
        for writing.
        """
        self.reactor.removeWriter(self)

    def startReading(self):
        """Start waiting for read availability.
        """
        self.reactor.addReader(self)

    def startWriting(self):
        """Start waiting for write availability.

        Call this to have this FileDescriptor be notified whenever it is ready for
        writing.
        """
        self.reactor.addWriter(self)

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
        if self.producer is not None:
            raise RuntimeError("Cannot register producer %s, because producer %s was never unregistered." % (producer, self.producer))
        if self.disconnected:
            producer.stopProducing()
        else:
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
        assert self.connected and not self.disconnecting
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
        return -1

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


__all__ = ["FileDescriptor"]
