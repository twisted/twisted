# -*- test-case-name: twisted.internet.test.test_pollingfile -*-
# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implements a simple polling interface for file descriptors that don't work with
C{select()} - this is pretty much only useful on Windows.
"""

import sys
from zope.interface import implements

import win32pipe
import win32file
import win32api
import pywintypes

from twisted.internet.interfaces import IConsumer, IPushProducer


MIN_TIMEOUT = 0.000000001
MAX_TIMEOUT = 0.1



class _PollableResource(object):

    active = True

    def activate(self):
        self.active = True


    def deactivate(self):
        self.active = False



class _PollingTimer(object):
    # Everything is private here because it is really an implementation detail.

    def __init__(self, reactor):
        self.reactor = reactor
        self._resources = []
        self._pollTimer = None
        self._currentTimeout = MAX_TIMEOUT
        self._paused = False

    def _addPollableResource(self, res):
        self._resources.append(res)
        self._checkPollingState()

    def _checkPollingState(self):
        for resource in self._resources:
            if resource.active:
                self._startPolling()
                break
        else:
            self._stopPolling()

    def _startPolling(self):
        if self._pollTimer is None:
            self._pollTimer = self._reschedule()

    def _stopPolling(self):
        if self._pollTimer is not None:
            self._pollTimer.cancel()
            self._pollTimer = None

    def _pause(self):
        self._paused = True

    def _unpause(self):
        self._paused = False
        self._checkPollingState()

    def _reschedule(self):
        if not self._paused:
            return self.reactor.callLater(self._currentTimeout, self._pollEvent)

    def _pollEvent(self):
        workUnits = 0.
        anyActive = []
        for resource in self._resources:
            if resource.active:
                workUnits += resource.checkWork()
                # Check AFTER work has been done
                if resource.active:
                    anyActive.append(resource)

        newTimeout = self._currentTimeout
        if workUnits:
            newTimeout = self._currentTimeout / (workUnits + 1.)
            if newTimeout < MIN_TIMEOUT:
                newTimeout = MIN_TIMEOUT
        else:
            newTimeout = self._currentTimeout * 2.
            if newTimeout > MAX_TIMEOUT:
                newTimeout = MAX_TIMEOUT
        self._currentTimeout = newTimeout
        if anyActive:
            self._pollTimer = self._reschedule()


# If we ever (let's hope not) need the above functionality on UNIX, this could
# be factored into a different module.


class _PollableReader(_PollableResource):

    implements(IPushProducer)

    def __init__(self, handle, receivedCallback, lostCallback):
        self.handle = handle
        self.receivedCallback = receivedCallback
        self.lostCallback = lostCallback

    def checkWork(self):
        raise NotImplementedError()

    def cleanup(self):
        self.deactivate()
        self.lostCallback()

    def close(self):
        # XXX why not cleanup?
        try:
            win32api.CloseHandle(self.handle)
        except pywintypes.error:
            # You can't close std handles...?
            pass

    def stopProducing(self):
        self.close()

    def pauseProducing(self):
        self.deactivate()

    def resumeProducing(self):
        self.activate()



class _PollableWriter(_PollableResource):
    FULL_BUFFER_SIZE = 64 * 1024

    implements(IConsumer)

    def __init__(self, handle, lostCallback):
        self.disconnecting = False
        self.producer = None
        self.producerPaused = 0
        self.streamingProducer = 0
        self.outQueue = []
        self.handle = handle
        self.lostCallback = lostCallback

    def close(self):
        self.disconnecting = True

    def bufferFull(self):
        if self.producer is not None:
            self.producerPaused = 1
            self.producer.pauseProducing()

    def bufferEmpty(self):
        if self.producer is not None and ((not self.streamingProducer) or
                                          self.producerPaused):
            self.producer.producerPaused = 0
            self.producer.resumeProducing()
            return True
        return False

    # almost-but-not-quite-exact copy-paste from abstract.FileDescriptor... ugh

    def registerProducer(self, producer, streaming):
        """Register to receive data from a producer.

        This sets this selectable to be a consumer for a producer.  When this
        selectable runs out of data on a write() call, it will ask the producer
        to resumeProducing(). A producer should implement the IProducer
        interface.

        FileDescriptor provides some infrastructure for producer methods.
        """
        if self.producer is not None:
            raise RuntimeError(
                "Cannot register producer %s, because producer %s was never "
                "unregistered." % (producer, self.producer))
        if not self.active:
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

    def writeConnectionLost(self):
        self.deactivate()
        try:
            win32api.CloseHandle(self.handle)
        except pywintypes.error:
            # OMG what
            pass
        self.lostCallback()

    def writeSequence(self, seq):
        self.outQueue.extend(seq)

    def write(self, data):
        if self.disconnecting:
            return
        self.outQueue.append(data)
        if sum(map(len, self.outQueue)) > self.FULL_BUFFER_SIZE:
            self.bufferFull()

    def checkWork(self):
        raise NotImplementedError()



class _PollableReadPipe(_PollableReader):
    def __init__(self, pipe, receivedCallback, lostCallback):
        _PollableReader.__init__(self, pipe, receivedCallback, lostCallback)
        # security attributes for pipes

    def checkWork(self):
        finished = 0
        fullDataRead = []

        while 1:
            try:
                buffer, bytesToRead, result = win32pipe.PeekNamedPipe(self.handle, 1)
                if not bytesToRead:
                    break
                hr, data = win32file.ReadFile(self.handle, bytesToRead, None)
                fullDataRead.append(data)
            except win32api.error:
                finished = 1
                break

        dataBuf = ''.join(fullDataRead)
        if dataBuf:
            self.receivedCallback(dataBuf)
        if finished:
            self.cleanup()
        return len(dataBuf)



class _PollableWritePipe(_PollableWriter):
    def __init__(self, writePipe, lostCallback):
        _PollableWriter.__init__(self, writePipe, lostCallback)

        try:
            win32pipe.SetNamedPipeHandleState(writePipe,
                                              win32pipe.PIPE_NOWAIT,
                                              None,
                                              None)
        except pywintypes.error:
            # Maybe it's an invalid handle.  Who knows.
            pass


    def checkWork(self):
        numBytesWritten = 0
        if not self.outQueue:
            if self.disconnecting:
                self.writeConnectionLost()
                return 0
            try:
                win32file.WriteFile(self.handle, '', None)
            except pywintypes.error:
                self.writeConnectionLost()
                return numBytesWritten
        while self.outQueue:
            data = self.outQueue.pop(0)
            errCode = 0
            if isinstance(data, unicode):
                raise TypeError("unicode not allowed")
            try:
                errCode, nBytesWritten = win32file.WriteFile(self.handle,
                                                             data, None)
            except win32api.error:
                self.writeConnectionLost()
                break
            else:
                # assert not errCode, "wtf an error code???"
                numBytesWritten += nBytesWritten
                if len(data) > nBytesWritten:
                    self.outQueue.insert(0, data[nBytesWritten:])
                    break
        else:
            resumed = self.bufferEmpty()
            if not resumed and self.disconnecting:
                self.writeConnectionLost()
        return numBytesWritten
