# -*- test-case-name: twisted.test.test_fifo -*-
# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
FIFO reading and writing support.

Maintainer: Mark Lvov
"""

import errno
import os

from zope.interface import implements

from twisted.internet.interfaces import IWriteDescriptor, IReadDescriptor
from twisted.internet.main import CONNECTION_LOST, CONNECTION_DONE
from twisted.internet.abstract import FileDescriptor
from twisted.internet.fdesc import writeToFD
from twisted.python.failure import Failure



class FIFOFileDescriptor(FileDescriptor):
    """
    An abstract base class, implementing common functionality for FIFO-related
    classes.

    @ivar path: Filesystem path of the FIFO
    @type path: L{FilePath<twisted.python.filepath.FilePath>}
    """

    def __init__(self, path, _reactor=None):
        self._fd = None
        self.path = path
        FileDescriptor.__init__(self, _reactor)


    def fileno(self):
        """
        Return the integer "file descriptor" for this FIFO
        """
        return self._fd


    def connectionLost(self, reason):
        """
        The connection was lost.
        """
        FileDescriptor.connectionLost(self, reason)
        self.protocol.connectionLost(reason)
        self.connected = 0
        if self._fd is not None:
            os.close(self._fd)

    def logPrefix(self):
        return "%s: %s" % (self.__class__.__name__, self.path.path)


class FIFOReader(FIFOFileDescriptor):
    """
    A reading end of a FIFO.
    """
    chunk_size = 8192
    implements(IReadDescriptor)

    def startReading(self):
        """
        Start waiting for read availability
        """
        if self.connected:
            FileDescriptor.startReading(self)
            return
        self._fd = os.open(self.path.path, os.O_RDONLY | os.O_NONBLOCK)
        self.connected = 1
        FileDescriptor.startReading(self)

    def startWriting(self):
        """
        Since this is a reader, it can not write to the FIFO
        """
        raise NotImplementedError("%s does not know how to write" %
                                  (self.__class__.__name__,))

    def doRead(self):
        """
        Data is available for reading on this FIFO
        """
        while True:
            try:
                output = os.read(self.fileno(), self.chunk_size)
            except (OSError, IOError), err:
                if err.args[0] in (errno.EAGAIN, errno.EINTR):
                    return
                else:
                    return CONNECTION_LOST
            if not output:
                return CONNECTION_DONE
            self.protocol.dataReceived(output)


    def loseConnection(self, _connDone=Failure(CONNECTION_DONE)):
        """
        Close the connection
        """
        if self.connected and not self.disconnecting:
            self.disconnecting = 1
            self.stopReading()
            self.reactor.callLater(0, self.connectionLost, _connDone)



class FIFOWriter(FIFOFileDescriptor):
    """
    A writing end of a FIFO.
    """
    implements(IWriteDescriptor)

    def startWriting(self):
        """
        Start waiting for write availability. Will raise L{OSError} with
        errno == ENXIO, if other end hasn't been opened (see fifo(7)).

        @raise OSError: if other end hasn't been opened (errno == ENXIO)
        """
        if self.connected:
            FileDescriptor.startWriting(self)
            return
        self._fd = os.open(self.path.path, os.O_WRONLY | os.O_NONBLOCK)
        self.connected = 1
        FileDescriptor.startWriting(self)


    def startReading(self):
        """
        Since this is a writer, it can not read from the FIFO
        """
        raise NotImplementedError("%s does not know how to read" %
                                  (self.__class__.__name__,))


    def writeSomeData(self, data):
        """
        Write data to the FIFO. Should not be used by protocols -
        use L{write<twisted.internet.abstract.FileDescriptor.write>} instead.
        """
        return writeToFD(self.fileno(), data)



def readFromFIFO(reactor, path, proto):
    """
    Start reading from the FIFO under a filesystem path C{path}.

    @param reactor: A reactor to use.

    @param path: Filesystem path of the FIFO
    @type path: L{FilePath<twisted.python.filepath.FilePath>}

    @param proto: A protocol to use.
    """
    fifo = FIFOReader(path, reactor)
    fifo.protocol = proto
    proto.makeConnection(fifo)
    # startReading comes last here, because we don't want to have a possibility
    # of losing data
    fifo.startReading()



def writeToFIFO(reactor, path, proto):
    """
    Start writing to the FIFO under a filesystem path C{path}.

    @param reactor: A reactor to use.

    @param path: Filesystem path of the FIFO
    @type path: L{FilePath<twisted.python.filepath.FilePath>}

    @param proto: A protocol to use.
    """
    fifo = FIFOWriter(path, reactor)
    fifo.protocol = proto
    fifo.startWriting()
    # makeConnection comes last here, because we can't allow the protocol to
    # start stuffing things into the fifo, before startWriting was called
    proto.makeConnection(fifo)
