# -*- test-case-name: twisted.internet.test.test_pollingfile -*-
# Copyright (c) Twisted Matrix Laboratories.
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

class Channel(object):
    def closeRead(self):
        raise NotImplementedError()

    def closeWrite(self):
        raise NotImplementedError()

    def read(self, size):
        raise NotImplementedError()

    def write(self, data):
        raise NotImplementedError()

    def isWriteClosed(self):
        raise NotImplementedError()

    def setEcho(self, enabled):
        raise NotImplementedError()


class ChannelReadPipe(Channel):
    def __init__(self, pipe):
        self.handle = pipe

    def read(self):
        _, bytesToRead, _ = win32pipe.PeekNamedPipe(self.handle, 1)
        if not bytesToRead:
            return ''
        _, data = win32file.ReadFile(self.handle, bytesToRead, None)
        return data

    def closeRead(self):
        try:
            win32api.CloseHandle(self.handle)
        except pywintypes.error:
            pass


class ChannelWritePipe(Channel):
    def __init__(self, pipe):
        self.handle = pipe
        try:
            win32pipe.SetNamedPipeHandleState(self.handle, win32pipe.PIPE_NOWAIT, None, None)
        except pywintypes.error:
            # Maybe it's an invalid handle.  Who knows.
            pass

    def write(self, data):
        try:
            _, bytesWritten = win32file.WriteFile(self.handle, data, None)
        except win32api.error:
            return None
        return bytesWritten

    def closeWrite(self):
        try:
            win32api.CloseHandle(self.handle)
        except pywintypes.error:
            pass

    def isWriteClosed(self):
        try:
            win32file.WriteFile(self.handle, '', None)
            return False
        except pywintypes.error:
            return True


class ChannelConsole(Channel):
    def __init__(self):
        import win32conio
        self.console = win32conio.Channel()

    def read(self):
        return self.console.read()

    def write(self, data):
        try:
            bytesWritten = self.console.write(data)
        except (pywintypes.error,), err:
            if err.winerror == 8:
                # 'Not enough storage is available to process this command.'
                raise ValueError(err.strerror)
            return None
        return bytesWritten

    def closeRead(self):
        self.console.closeRead()

    def closeWrite(self):
        self.console.closeWrite()

    def isWriteClosed(self):
        return self.console.isWriteClosed()

    def setEcho(self, enabled):
        self.console.setEcho(enabled)


class _PollableReader(_PollableResource):

    implements(IPushProducer)

    def __init__(self, channel, receivedCallback, lostCallback):
        self.channel = channel
        self.receivedCallback = receivedCallback
        self.lostCallback = lostCallback

    def checkWork(self):
        finished = 0
        fullDataRead = []
        while 1:
            try:
                data = self.channel.read()
                if not data:
                    break
                fullDataRead.append(data)
            except pywintypes.error:
                finished = 1
                break
        dataBuf = ''.join(fullDataRead)
        if dataBuf:
            self.receivedCallback(dataBuf)
        if finished:
            self.cleanup()
        return len(dataBuf)

    def cleanup(self):
        self.deactivate()
        self.lostCallback()

    def close(self):
        self.channel.closeRead()

    def stopProducing(self):
        self.close()

    def pauseProducing(self):
        self.deactivate()

    def resumeProducing(self):
        self.activate()



class _PollableWriter(_PollableResource):
    FULL_BUFFER_SIZE = 64 * 1024

    implements(IConsumer)

    def __init__(self, channel, lostCallback):
        self.disconnecting = False
        self.producer = None
        self.producerPaused = False
        self.streamingProducer = 0
        self.outQueue = []
        self.channel = channel
        self.lostCallback = lostCallback

    def close(self):
        self.disconnecting = True
        self.checkWork()

    def bufferFull(self):
        if self.producer is not None:
            self.producerPaused = True
            self.producer.pauseProducing()

    def bufferEmpty(self):
        if self.producer is not None and ((not self.streamingProducer) or
                                          self.producerPaused):
            self.producer.producerPaused = False
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
        self.channel.closeWrite()
        self.lostCallback()

    def writeSequence(self, seq):
        if self.disconnecting:
            return
        self.outQueue.extend(seq)
        if sum(map(len, self.outQueue)) > self.FULL_BUFFER_SIZE:
            self.bufferFull()
        self.checkWork()

    def write(self, data):
        if self.disconnecting:
            return
        self.outQueue.append(data)
        if sum(map(len, self.outQueue)) > self.FULL_BUFFER_SIZE:
            self.bufferFull()
        self.checkWork()

    def checkWork(self):
        if not self.outQueue:
            if self.disconnecting or self.channel.isWriteClosed():
                self.writeConnectionLost()
                return 0
        totalBytesWritten = 0
        while self.outQueue:
            data = self.outQueue.pop(0)
            if isinstance(data, unicode):
                raise TypeError("unicode not allowed")

            try:
                bytesWritten = self.channel.write(data)
            except ValueError:
                # WriteConsole() has variable buffer length limitations.
                # Split data into two (roughly), put back into queue and
                # try again.
                len2 = len(data)/2
                d1, d2 = data[:len2], data[len2:]
                self.outQueue.insert(0, d2)
                self.outQueue.insert(0, d1)
                continue
            if bytesWritten is None:        # error occurred
                self.writeConnectionLost()
                break
            totalBytesWritten += bytesWritten
            if len(data) > bytesWritten:
                self.outQueue.insert(0, data[bytesWritten:])
                break
        else:
            resumed = self.bufferEmpty()
            if not resumed and self.disconnecting:
                self.writeConnectionLost()
        return totalBytesWritten


# _pollingfile support
class _PollableReadConsole(_PollableReader):
    def __init__(self, channelConsole, receivedCallback, lostCallback):
        _PollableReader.__init__(self, channelConsole, receivedCallback, lostCallback) 


class _PollableReadPipe(_PollableReader):
    def __init__(self, handle, receivedCallback, lostCallback):
        _PollableReader.__init__(self, ChannelReadPipe(handle), receivedCallback, lostCallback)


class _PollableWriteConsole(_PollableWriter):
    def __init__(self, channelConsole, lostCallback):
        _PollableWriter.__init__(self, channelConsole, lostCallback)


class _PollableWritePipe(_PollableWriter):
    def __init__(self, handle, lostCallback):
        _PollableWriter.__init__(self, ChannelWritePipe(handle), lostCallback)

