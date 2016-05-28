"""
Tulip-based reactor implementation.
"""

try:
    from asyncio import get_event_loop, new_event_loop
except ImportError:
    # Try importing trollius, the Python 2 backport of asyncio, if asyncio
    # is not found.
    from trollius import get_event_loop, new_event_loop

from zope.interface import implementer

from twisted.internet.base import DelayedCall
from twisted.internet.posixbase import PosixReactorBase
from twisted.python.log import callWithLogger
from twisted.internet.interfaces import IReactorFDSet


class _DCHandle(object):
    """
    Wrapper for asyncio.Handle to be used by DelayedCall.
    """
    def __init__(self, handle):
        self.handle = handle

    def cancel(self):
        self.handle.cancel()


@implementer(IReactorFDSet)
class AsyncioSelectorReactor(PosixReactorBase):
    """
    Reactor running on top of an asyncio SelectorEventLoop.
    """
    _asyncClosed = False

    def __init__(self, eventloop):
        self._asyncioEventloop = eventloop
        self._writers = set()
        self._readers = set()
        self._delayedCalls = set()
        PosixReactorBase.__init__(self)

    def _read_or_write(self, selectable, read):
        method = selectable.doRead if read else selectable.doWrite
        try:
            why = method()
        except Exception as e:
            why = e
        if why:
            self._disconnectSelectable(selectable, why, read)

    def addReader(self, reader):
        self._readers.add(reader)
        fd = reader.fileno()
        self._asyncioEventloop.add_reader(fd, callWithLogger, reader,
                                          self._read_or_write, reader, True)

    def addWriter(self, writer):
        self._writers.add(writer)
        fd = writer.fileno()
        self._asyncioEventloop.add_writer(fd, callWithLogger, writer,
                                          self._read_or_write, writer, False)

    def removeReader(self, reader):
        try:
            self._readers.remove(reader)
        except KeyError:
            pass
        fd = reader.fileno()
        if fd == -1:
            return
        self._asyncioEventloop.remove_reader(fd)

    def removeWriter(self, writer):
        try:
            self._writers.remove(writer)
        except KeyError:
            pass
        fd = writer.fileno()
        if fd == -1:
            return
        self._asyncioEventloop.remove_writer(fd)

    def removeAll(self):
        return self._removeAll(self._readers, self._writers)

    def getReaders(self):
        return list(self._readers)

    def getWriters(self):
        return list(self._writers)

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
        PosixReactorBase.stop(self)
        self.callLater(0, self.fireSystemEvent, "shutdown")

    def crash(self):
        PosixReactorBase.crash(self)
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
    callFromThread = callWhenRunning


# Install some testing infrastructure; please don't look at this:
@staticmethod
def _reactorForTesting():
    loop = new_event_loop()
    loop.set_debug(True)
    return AsyncioSelectorReactor(loop)
def _installTestInfrastructure():
    from twisted.internet.test.reactormixins import ReactorBuilder
    ReactorBuilder._reactors.append("txtulip.reactor._reactorForTesting")
_installTestInfrastructure()


def install(eventloop=None):
    """
    Install a tulip-based reactor.
    """
    if eventloop is None:
        eventloop = get_event_loop()
    reactor = AsyncioSelectorReactor(eventloop)
    from twisted.internet.main import installReactor
    installReactor(reactor)
