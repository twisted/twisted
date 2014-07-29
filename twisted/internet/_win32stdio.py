# -*- test-case-name: twisted.test.test_stdio -*-

"""
Windows-specific implementation of the L{twisted.internet.stdio} interface.
"""

import win32api
import os, msvcrt

from zope.interface import implements

from twisted.internet.interfaces import IHalfCloseableProtocol, ITransport, IAddress
from twisted.internet.interfaces import IConsumer, IPushProducer

from twisted.internet import _pollingfile, main
from twisted.python.failure import Failure


class Win32PipeAddress(object):
    implements(IAddress)



class StandardIO(_pollingfile._PollingTimer):

    implements(ITransport,
               IConsumer,
               IPushProducer)

    disconnecting = False
    disconnected = False

    def __init__(self, proto, stdin=0, stdout=1, reactor=None):
        """
        Start talking to standard IO with the given protocol.

        The stdin/stdout params are file descriptors (integers), e.g. as
        returned by the fileno() method of a Python file object. On windows,
        they may represent open files or pipes. Both of these will be put
        into binary mode.
        """
        if reactor is None:
            from twisted.internet import reactor

        for fd in (stdin, stdout):
            msvcrt.setmode(fd, os.O_BINARY)

        _pollingfile._PollingTimer.__init__(self, reactor)
        self.proto = proto

        hstdin = msvcrt.get_osfhandle(stdin)
        hstdout = msvcrt.get_osfhandle(stdout)

        self.stdin = _pollingfile._PollableReadPipe(
            hstdin, self.dataReceived, self.readConnectionLost)

        self.stdout = _pollingfile._PollableWritePipe(
            hstdout, self.writeConnectionLost)

        self._addPollableResource(self.stdin)
        self._addPollableResource(self.stdout)

        self.proto.makeConnection(self)

    def dataReceived(self, data):
        self.proto.dataReceived(data)

    def readConnectionLost(self):
        if IHalfCloseableProtocol.providedBy(self.proto):
            self.proto.readConnectionLost()
        self.checkConnLost()

    def writeConnectionLost(self):
        if IHalfCloseableProtocol.providedBy(self.proto):
            self.proto.writeConnectionLost()
        self.checkConnLost()

    connsLost = 0

    def checkConnLost(self):
        self.connsLost += 1
        if self.connsLost >= 2:
            self.disconnecting = True
            self.disconnected = True
            self.proto.connectionLost(Failure(main.CONNECTION_DONE))

    # ITransport

    def write(self, data):
        self.stdout.write(data)

    def writeSequence(self, seq):
        self.stdout.write(''.join(seq))

    def loseConnection(self):
        self.disconnecting = True
        self.stdin.close()
        self.stdout.close()

    def getPeer(self):
        return Win32PipeAddress()

    def getHost(self):
        return Win32PipeAddress()

    # IConsumer

    def registerProducer(self, producer, streaming):
        return self.stdout.registerProducer(producer, streaming)

    def unregisterProducer(self):
        return self.stdout.unregisterProducer()

    # def write() above

    # IProducer

    def stopProducing(self):
        self.stdin.stopProducing()

    # IPushProducer

    def pauseProducing(self):
        self.stdin.pauseProducing()

    def resumeProducing(self):
        self.stdin.resumeProducing()

