# -*- test-case-name: twisted.test.test_process.ProcessTestCase.testStdio,twisted.test.test_conio.StdIOTestCase -*-

# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Windows-specific implementation of the L{twisted.internet.stdio} interface.
"""
import os
import errno
import msvcrt

import pywintypes
import win32api
import win32console

from zope.interface import implements

from twisted.internet.interfaces import IHalfCloseableProtocol, ITransport, IAddress
from twisted.internet.interfaces import IConsumer, IPushProducer
from twisted.internet import main, abstract

import _pollingfile
from twisted.python.failure import Failure



# _pollingfile support
# XXX check me
class _PollableReadConsole(_pollingfile._PollableReader):
    def __init__(self, channel, receivedCallback, lostCallback):
        _pollingfile._PollableReader.__init__(self, channel.handle,
                                              receivedCallback, lostCallback) 
        self.channel = channel

    def checkWork(self):
        try:
            data = self.channel.read(2000) # 2000 = 80 x 25
        except IOError, ioe:
            assert ioe.args[0] == errno.EAGAIN
            return 0
        except win32console.error:
            # stdin or stdout closed?
            self.cleanup()
            return 0

        self.receivedCallback(data)
        return len(data)


class _PollableWriteConsole(_pollingfile._PollableWriter):
    def __init__(self, channel, lostCallback):
        _pollingfile._PollableWriter.__init__(self, channel.handle, lostCallback)

        self.channel = channel

    def checkWork(self):
        numBytesWritten = 0
        if not self.outQueue:
            if self.disconnecting:
                self.writeConnectionLost()
                return 0
            try:
                self.channel.write('')
            except pywintypes.error:
                self.writeConnectionLost()
                return numBytesWritten

        while self.outQueue:
            data = self.outQueue.pop(0)
            try:
                # XXX as far as I know, 
                # nBytesWritten is always equal to len(data)
                nBytesWritten = self.channel.write(data)
            except win32console.error:
                self.writeConnectionLost()
                break
            else:
                numBytesWritten += nBytesWritten
                if len(data) > nBytesWritten:
                    self.outQueue.insert(0, data[nBytesWritten:])
                    break
        else:
            resumed = self.bufferEmpty()
            if not resumed and self.disconnecting:
                self.writeConnectionLost()

        return numBytesWritten



# support for win32eventreactor
# XXX check me
class ConsoleReader(abstract.FileDescriptor):
    def __init__(self, channel, receivedCallback, lostCallback, reactor=None):
        """win32eventreactor is assumed.
        """
        
        if not reactor:
            from twisted.internet import reactor

        self.channel = channel
        self.receivedCallback = receivedCallback
        self.lostCallback = lostCallback
        self.reactor = reactor

        self.reactor.addEvent(self.channel.handle, self, "doRead")


    def doRead(self):
        try:
            data = self.channel.read(2000) # 2000 = 80 x 25
        except IOError, ioe:
            assert ioe.args[0] == errno.EAGAIN
            return 0
        except win32console.error:
            # stdin or stdout closed?
            self.cleanup()
            return 0

        self.receivedCallback(data)
        return len(data)

    def cleanup(self):
        self.reactor.removeEvent(self.channel.handle)
        self.lostCallback()

    def close(self):
        try:
            win32api.CloseHandle(self.channel.handle)
        except pywintypes.error:
            # You can't close std handles...?
            pass

        self.cleanup()

    def stopProducing(self):
        self.close()

    def pauseProducing(self):
        self.reactor.removeEvent(self.channel.handle)

    def resumeProducing(self):
        self.reactor.addEvent(self.channel.handle, self, "doRead")


class Win32PipeAddress(object):
    implements(IAddress)

class Win32ConsoleAddress(object):
    implements(IAddress)


class StandardIO(_pollingfile._PollingTimer):

    implements(ITransport,
               IConsumer,
               IPushProducer)

    disconnecting = False
    disconnected = False

    def __init__(self, proto):
        """
        Start talking to standard IO with the given protocol.

        Also, put it stdin/stdout/stderr into binary mode.
        """

        from twisted.internet import reactor
        from twisted.internet.win32eventreactor import Win32Reactor
        
        for stdfd in (0, 1, 2):
            msvcrt.setmode(stdfd, os.O_BINARY)

        _pollingfile._PollingTimer.__init__(self, reactor)
        self.proto = proto
        
        # Check for win32eventreactor
        win32EventReactorInstalled = reactor.__class__ is Win32Reactor

        # Check if we are connected to a console.
        # If this is the case, connect to the console, else connect to
        # anonymous pipes.
        if os.isatty(0):
            import win32conio
            
            if win32EventReactorInstalled:
                self.stdin = ConsoleReader(
                    win32conio.stdin, self.dataReceived, self.readConnectionLost
                    )
            else:
                self.stdin = _PollableReadConsole(
                    win32conio.stdin, self.dataReceived, self.readConnectionLost
                    )
        else:
            hstdin = win32api.GetStdHandle(win32api.STD_INPUT_HANDLE)
            self.stdin = _pollingfile._PollableReadPipe(
                hstdin, self.dataReceived, self.readConnectionLost
                )

        if os.isatty(1):
            import win32conio
            
            self.stdout = _PollableWriteConsole(
                win32conio.stdout, self.writeConnectionLost
                )
        else:
            hstdout = win32api.GetStdHandle(win32api.STD_OUTPUT_HANDLE)
            self.stdout = _pollingfile._PollableWritePipe(
                hstdout, self.writeConnectionLost
                )
            
        if not (os.isatty(0) and win32EventReactorInstalled):
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
        if os.isatty(0) and os.isatty(1):
            return Win32ConsoleAddress()
        else:
            return Win32PipeAddress()

    def getHost(self):
        if os.isatty(0) and os.isatty(1):
            return Win32ConsoleAddress()
        else:
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
