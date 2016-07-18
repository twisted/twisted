# -*- test-case-name: twisted.test.test_internet -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
asyncio-based reactor implementation.
"""

from __future__ import absolute_import, division

import errno

from zope.interface import implementer

from twisted.logger import Logger
from twisted.internet.base import DelayedCall
from twisted.internet.posixbase import (PosixReactorBase, _NO_FILEDESC,
                                        _ContinuousPolling)
from twisted.python.log import callWithLogger
from twisted.internet.interfaces import IReactorFDSet

try:
    from asyncio import new_event_loop
except ImportError:
    try:
        from trollius import new_event_loop
    except ImportError:
        raise ImportError("Requires asyncio or trollius.")



class _DCHandle(object):
    """
    Wrapper for L{asyncio.Handle} to be used by
    L{twisted.internet.base.DelayedCall}.
    """
    def __init__(self, handle):
        self.handle = handle


    def cancel(self):
        """
        Cancel the inner L{asyncio.Handle}.
        """
        self.handle.cancel()



@implementer(IReactorFDSet)
class AsyncioSelectorReactor(PosixReactorBase):
    """
    Reactor running on top of L{asyncio.SelectorEventLoop}.
    """
    _asyncClosed = False
    _log = Logger()

    def __init__(self, eventloop=None):

        if eventloop is None:
            eventloop = new_event_loop()

        self._asyncioEventloop = eventloop
        self._writers = {}
        self._readers = {}
        self._delayedCalls = set()
        self._continuousPolling = _ContinuousPolling(self)
        super(AsyncioSelectorReactor, self).__init__()


    def _readOrWrite(self, selectable, read):
        method = selectable.doRead if read else selectable.doWrite

        if selectable.fileno() == -1:
            self._disconnectSelectable(selectable, _NO_FILEDESC, read)
            return

        try:
            why = method()
        except Exception as e:
            why = e
            self._log.failure(None)
        if why:
            self._disconnectSelectable(selectable, why, read)


    def addReader(self, reader):
        if reader in self._readers.keys() or \
           reader in self._continuousPolling._readers:
            return

        fd = reader.fileno()
        try:
            self._asyncioEventloop.add_reader(fd, callWithLogger, reader,
                                              self._readOrWrite, reader,
                                              True)
            self._readers[reader] = fd
        except IOError as e:
            if e.errno == errno.EPERM:
                # epoll(7) doesn't support certain file descriptors,
                # e.g. filesystem files, so for those we just poll
                # continuously:
                self._continuousPolling.addReader(reader)
            else:
                raise


    def addWriter(self, writer):
        if writer in self._writers.keys() or \
           writer in self._continuousPolling._writers:
            return

        fd = writer.fileno()
        try:
            self._asyncioEventloop.add_writer(fd, callWithLogger, writer,
                                              self._readOrWrite, writer,
                                              False)
            self._writers[writer] = fd
        except IOError as e:
            if e.errno == errno.EPERM:
                # epoll(7) doesn't support certain file descriptors,
                # e.g. filesystem files, so for those we just poll
                # continuously:
                self._continuousPolling.addWriter(writer)
            else:
                raise


    def removeReader(self, reader):

        # First, see if they're trying to remove a reader that we don't have.
        if not (reader in self._readers.keys() \
                or self._continuousPolling.isReading(reader)):
            # We don't have it, so just return OK.
            return

        # If it was a cont. polling reader, check there first.
        if self._continuousPolling.isReading(reader):
            self._continuousPolling.removeReader(reader)
            return

        fd = reader.fileno()
        if fd == -1:
            # If the FD is -1, we want to know what its original FD was, to
            # remove it.
            fd = self._readers.pop(reader)
        else:
            self._readers.pop(reader)

        self._asyncioEventloop.remove_reader(fd)


    def removeWriter(self, writer):

        # First, see if they're trying to remove a writer that we don't have.
        if not (writer in self._writers.keys() \
                or self._continuousPolling.isWriting(writer)):
            # We don't have it, so just return OK.
            return

        # If it was a cont. polling writer, check there first.
        if self._continuousPolling.isWriting(writer):
            self._continuousPolling.removeWriter(writer)
            return

        fd = writer.fileno()

        if fd == -1:
            # If the FD is -1, we want to know what its original FD was, to
            # remove it.
            fd = self._writers.pop(writer)
        else:
            self._writers.pop(writer)

        self._asyncioEventloop.remove_writer(fd)


    def removeAll(self):
        return (self._removeAll(self._readers.keys(), self._writers.keys()) +
                self._continuousPolling.removeAll())


    def getReaders(self):
        return (list(self._readers.keys()) +
                self._continuousPolling.getReaders())


    def getWriters(self):
        return (list(self._writers.keys()) +
                self._continuousPolling.getWriters())


    def getDelayedCalls(self):
        return list(self._delayedCalls)


    def iterate(self, timeout):
        self._asyncioEventloop.call_later(timeout + 0.01,
                                          self._asyncioEventloop.stop)
        self._asyncioEventloop.run_forever()


    def run(self, installSignalHandlers=True):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self._asyncioEventloop.run_forever()
        if self._justStopped:
            self._justStopped = False


    def stop(self):
        super(AsyncioSelectorReactor, self).stop()
        self.callLater(0, self.fireSystemEvent, "shutdown")


    def crash(self):
        super(AsyncioSelectorReactor, self).crash()
        self._asyncioEventloop.stop()


    def seconds(self):
        return self._asyncioEventloop.time()


    def callLater(self, seconds, f, *args, **kwargs):
        def run():
            dc.called = True
            self._delayedCalls.remove(dc)
            f(*args, **kwargs)
        handle = self._asyncioEventloop.call_later(seconds, run)
        dchandle = _DCHandle(handle)

        def cancel(dc):
            self._delayedCalls.remove(dc)
            dchandle.cancel()

        def reset(dc):
            dchandle.handle = self._asyncioEventloop.call_at(dc.time, run)

        dc = DelayedCall(self.seconds() + seconds, run, (), {},
                         cancel, reset, seconds=self.seconds)
        self._delayedCalls.add(dc)
        return dc


    def callWhenRunning(self, f, *args, **kwargs):
        g = lambda: f(*args, **kwargs)
        self._asyncioEventloop.call_soon_threadsafe(g)


    def callFromThread(self, f, *args, **kwargs):
        g = lambda: self.callLater(0, f, *args, **kwargs)
        self._asyncioEventloop.call_soon_threadsafe(g)



def install(eventloop=None):
    """
    Install an asyncio-based reactor.

    @param eventloop: The asyncio eventloop to wrap. If default, the global one
        is selected.
    """
    reactor = AsyncioSelectorReactor(eventloop)
    from twisted.internet.main import installReactor
    installReactor(reactor)
