# -*- test-case-name: twisted.test.test_process.ProcessTestCase.testStdio -*-

from twisted.internet.interfaces import IHalfCloseableProtocol

from twisted.internet import _pollingfile, main

import win32api

class StandardIO(_pollingfile._PollingTimer):
    def __init__(self, proto):
        from twisted.internet import reactor
        _pollingfile._PollingTimer.__init__(self, reactor)
        self.proto = proto

        hstdin = win32api.GetStdHandle(win32api.STD_INPUT_HANDLE)
        hstdout = win32api.GetStdHandle(win32api.STD_OUTPUT_HANDLE)

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
            self.proto.connectionLost(main.CONNECTION_DONE)

    def write(self, data):
        self.stdout.write(data)

    def loseConnection(self):
        self.stdin.close()
        self.stdout.close()

