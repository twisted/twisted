# -*- test-case-name: twisted.test.test_process.ProcessTestCase.testStdio,twisted.test.test_conio.StdIOTestCase -*-

# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Windows-specific implementation of the L{twisted.internet.stdio} interface.
"""
import os
import sys
import errno
import msvcrt
import time

import pywintypes
import win32api

from zope.interface import implements

from twisted.internet.interfaces import IHalfCloseableProtocol, ITransport, IAddress
from twisted.internet.interfaces import IConsumer, IPushProducer
from twisted.internet import main, abstract

import _pollingfile
from twisted.python.failure import Failure


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

    # TODO
    def __init__(self, proto, forceConsole=False, reactor=None):
        """
        Start talking to standard IO with the given protocol.

        Also, put stdin/stdout/stderr into binary mode.
        """
        if reactor is None:
            from twisted.internet import reactor
        
        for stdfd in (0, 1, 2):
            msvcrt.setmode(stdfd, os.O_BINARY)

        _pollingfile._PollingTimer.__init__(self, reactor)
        self.proto = proto
        
        # Check if we are connected to a console.
        # If this is the case, connect to the console, else connect to
        # anonymous pipes.
        if forceConsole or os.isatty(0) or os.isatty(1) or os.isatty(2):
            import win32conio
            console = win32conio.Console()
            self.stdin = _pollingfile._PollableReadConsole(
                console, self.dataReceived, self.readConnectionLost
                )
            self.stdout = _pollingfile._PollableWriteConsole(
                console, self.writeConnectionLost
                )
            self.stderr = None
            self._disconnectCount = 2
        else:
            hstdin = win32api.GetStdHandle(win32api.STD_INPUT_HANDLE)
            self.stdin = _pollingfile._PollableReadPipe(
                hstdin, self.dataReceived, self.readConnectionLost
                )
            hstdout = win32api.GetStdHandle(win32api.STD_OUTPUT_HANDLE)
            self.stdout = _pollingfile._PollableWritePipe(
                hstdout, self.writeConnectionLost
                )
            hstderr = win32api.GetStdHandle(win32api.STD_ERROR_HANDLE)
            self.stderr = _pollingfile._PollableWritePipe(
                hstderr, self.writeConnectionLost
                )
            self._disconnectCount = 3
            self._addPollableResource(self.stderr)

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
        if self.connsLost >= self._disconnectCount:
            self.disconnecting = True
            self.disconnected = True
            self.proto.connectionLost(Failure(main.CONNECTION_DONE))

    # ITransport

    # XXX Actually, see #3597.
    def loseWriteConnection(self):
        self.stdout.close()

    def write(self, data):
        self.stdout.write(data)

    def writeSequence(self, seq):
        self.stdout.write(''.join(seq))

    def loseConnection(self):
        self.disconnecting = True
        self.disconnected = True
        self.stdin.close()
        self.stdout.close()
        if self.stderr:
            self.stderr.close()

    def setEcho(self, enabled):
        self.stdin.channel.setEcho(enabled)

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

