# -*- test-case-name: twisted.test.test_internet -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Threaded select reactor

The threadedselectreactor is a specialized reactor for integrating with
arbitrary foreign event loop, such as those you find in GUI toolkits.

There are three things you'll need to do to use this reactor.

Install the reactor at the beginning of your program, before importing the rest
of Twisted::

    | from twisted.internet import _threadedselect
    | _threadedselect.install()

Interleave this reactor with your foreign event loop, at some point after your
event loop is initialized::

    | from twisted.internet import reactor
    | reactor.interleave(foreignEventLoopWakerFunction)
    | self.addSystemEventTrigger('after', 'shutdown', foreignEventLoopStop)

Instead of shutting down the foreign event loop directly, shut down the
reactor::

    | from twisted.internet import reactor
    | reactor.stop()

In order for Twisted to do its work in the main thread (the thread that
interleave is called from), a waker function is necessary.  The waker function
will be called from a "background" thread with one argument: func.  The waker
function's purpose is to call func() from the main thread.  Many GUI toolkits
ship with appropriate waker functions.  One example of this is wxPython's
wx.callAfter (may be wxCallAfter in older versions of wxPython).  These would
be used in place of "foreignEventLoopWakerFunction" in the above example.

The other integration point at which the foreign event loop and this reactor
must integrate is shutdown.  In order to ensure clean shutdown of Twisted, you
must allow for Twisted to come to a complete stop before quitting the
application.  Typically, you will do this by setting up an after shutdown
trigger to stop your foreign event loop, and call reactor.stop() where you
would normally have initiated the shutdown procedure for the foreign event
loop.  Shutdown functions that could be used in place of "foreignEventloopStop"
would be the ExitMainLoop method of the wxApp instance with wxPython.
"""

from errno import EBADF, EINTR
from functools import partial
from queue import Empty, Queue
from threading import Thread
from typing import Any

from zope.interface import implementer

from twisted.internet import posixbase
from twisted.internet.interfaces import IReactorFDSet, IReadDescriptor, IWriteDescriptor
from twisted.internet.posixbase import _NO_FILEDESC
from twisted.internet.selectreactor import _preenDescriptors, _select
from twisted.logger import Logger
from twisted.python import failure, threadable
from twisted.python.log import callWithLogger as _callWithLogger

_log = Logger()


def raiseException(e):
    raise e


@implementer(IReactorFDSet)
class ThreadedSelectReactor(posixbase.PosixReactorBase):
    """A threaded select() based reactor - runs on all POSIX platforms and on
    Win32.
    """

    def __init__(self) -> None:
        threadable.init(1)
        self.reads: set[IReadDescriptor] = set()
        self.writes: set[IWriteDescriptor] = set()
        self.toThreadQueue: Queue[Any] = Queue()
        self.toMainThread: Queue[Any] = Queue()
        self.workerThread = None
        self.mainWaker = None
        posixbase.PosixReactorBase.__init__(self)
        self.addSystemEventTrigger("after", "shutdown", self._mainLoopShutdown)

    def wakeUp(self):
        # we want to wake up from any thread
        self.waker.wakeUp()

    def callLater(self, *args, **kw):
        tple = posixbase.PosixReactorBase.callLater(self, *args, **kw)
        self.wakeUp()
        return tple

    def _sendToMain(self, msg, *args):
        self.toMainThread.put((msg, args))
        if self.mainWaker is not None:
            self.mainWaker()

    def _sendToThread(self, fn, *args):
        self.toThreadQueue.put((fn, args))

    def _workerInThread(self):
        try:
            while 1:
                fn, args = self.toThreadQueue.get()
                fn(*args)
        except SystemExit:
            pass  # Exception indicates this thread should exit
        except BaseException:
            f = failure.Failure()
            self._sendToMain("Failure", f)

    def _doIterationInThread(
        self, timeout: float, readmap: dict[int, object], writemap: dict[int, object]
    ) -> None:
        """Run one iteration of the I/O monitor loop.

        This will run all selectables who had input or output readiness
        waiting for them.
        """
        preen = False
        r = []
        w = []
        while 1:
            readints = readmap.keys()
            writeints = writemap.keys()
            try:
                result = _select(readints, writeints, [], timeout)
            except (ValueError, TypeError):
                # Possible problems with file descriptors that were passed:
                # ValueError may indicate that a file descriptor has gone
                # negative, and TypeError indicates that something *totally*
                # invalid (an object without a .fileno method, or such a method
                # with a result that has a type other than `int`) was passed.
                # This is probably a bug in application code that we *can*
                # recover from, so we will log it and try to do that.
                preen = True
                break
            except OSError as se:
                # The select() system call encountered an error.
                if se.args[0] in (0, 2):
                    # windows does this if it got an empty list
                    if (len(readmap) + len(writemap)) == 0:
                        return
                    else:
                        raise
                elif se.args[0] == EINTR:
                    return
                elif se.args[0] == EBADF:
                    preen = True
                    break
                else:
                    # OK, I really don't know what's going on.  Blow up.
                    raise
            else:
                r, w, ignored = result
                break
        _log.info("end thread, back to main")
        self._sendToMain("Notify", r, w, preen, readmap, writemap)

    def _process_Notify(
        self,
        r: list[int],
        w: list[int],
        preen: bool,
        readmap: dict[int, IReadDescriptor],
        writemap: dict[int, IWriteDescriptor],
    ) -> None:
        if preen:
            _preenDescriptors(self.reads, self.writes, self._disconnectSelectable)
            return
        _drdw = self._doReadOrWrite
        for readable in r:
            rselectable = readmap[readable]
            _callWithLogger(rselectable, _drdw, rselectable, "doRead")
        for writable in w:
            wselectable = writemap[writable]
            _callWithLogger(wselectable, _drdw, wselectable, "doWrite")

    def _process_Failure(self, f):
        f.raiseException()

    def ensureWorkerThread(self):
        if self.workerThread is None or not self.workerThread.isAlive():
            self.workerThread = Thread(target=self._workerInThread)
            self.workerThread.start()

    def _mapOneEntry(self, selectable: Any) -> int | None:
        with _log.handlingFailures("determining fileno for selectability"):
            fd: int = selectable.fileno()
            return fd
        return None  # type:ignore[unreachable]

    def _dispatchIteration(self, timeout: float) -> None:
        reads: dict[int, object] = {}
        writes: dict[int, object] = {}
        for isRead, fdmap, d in [
            (True, self.reads, reads),
            (False, self.writes, writes),
        ]:
            for each in fdmap:  # type:ignore[attr-defined]
                asfd = self._mapOneEntry(each)
                if asfd is None:
                    self._disconnectSelectable(each, _NO_FILEDESC, isRead)
                else:
                    d[asfd] = each
        self._sendToThread(self._doIterationInThread, timeout, reads, writes)

    def doThreadIteration(self, timeout):
        self._dispatchIteration(timeout)
        self.ensureWorkerThread()
        msg, args = self.toMainThread.get()
        getattr(self, "_process_" + msg)(*args)

    doIteration = doThreadIteration

    def _interleave(self):
        while self.running:
            self.runUntilCurrent()
            t2 = self.timeout()
            t = self.running and t2
            self._dispatchIteration(t)
            yield None
            msg, args = self.toMainThread.get_nowait()
            getattr(self, "_process_" + msg)(*args)

    def interleave(self, waker, *args, **kw):
        """
        interleave(waker) interleaves this reactor with the
        current application by moving the blocking parts of
        the reactor (select() in this case) to a separate
        thread.  This is typically useful for integration with
        GUI applications which have their own event loop
        already running.

        See the module docstring for more information.
        """
        self.startRunning(*args, **kw)
        loop = self._interleave()

        def mainWaker(waker=waker, loop=loop):
            waker(partial(next, loop))

        self.mainWaker = mainWaker
        next(loop)
        self.ensureWorkerThread()

    def _mainLoopShutdown(self):
        self.mainWaker = None
        if self.workerThread is not None:
            self._sendToThread(raiseException, SystemExit)
            self.wakeUp()
            try:
                while 1:
                    msg, args = self.toMainThread.get_nowait()
            except Empty:
                pass
            self.workerThread.join()
            self.workerThread = None
        try:
            while 1:
                fn, args = self.toThreadQueue.get_nowait()
                if fn is self._doIterationInThread:
                    _log.warn(
                        "possible threadedselectreactor bug: iteration is still in the thread queue!"
                    )
                elif fn is raiseException and args[0] is SystemExit:
                    pass
                else:
                    fn(*args)
        except Empty:
            pass

    def _doReadOrWrite(self, selectable, method):
        with _log.handlingFailures(
            "while handling selectable {sel}", sel=selectable
        ) as op:
            why = getattr(selectable, method)()
        if op.failed:
            why = op.failure.value
        if why:
            self._disconnectSelectable(selectable, why, method == "doRead")

    def addReader(self, reader: IReadDescriptor) -> None:
        """Add a FileDescriptor for notification of data available to read."""
        self.reads.add(reader)
        self.wakeUp()

    def addWriter(self, writer: IWriteDescriptor) -> None:
        """Add a FileDescriptor for notification of data available to write."""
        self.writes.add(writer)
        self.wakeUp()

    def removeReader(self, reader: IReadDescriptor) -> None:
        """Remove a Selectable for notification of data available to read."""
        if reader in self.reads:
            self.reads.remove(reader)

    def removeWriter(self, writer: IWriteDescriptor) -> None:
        """Remove a Selectable for notification of data available to write."""
        if writer in self.writes:
            self.writes.remove(writer)

    def removeAll(self) -> list[IReadDescriptor | IWriteDescriptor]:
        return self._removeAll(self.reads, self.writes)  # type:ignore[no-any-return]

    def getReaders(self) -> list[IReadDescriptor]:
        return list(self.reads)

    def getWriters(self) -> list[IWriteDescriptor]:
        return list(self.writes)

    def stop(self):
        """
        Extend the base stop implementation to also wake up the select thread so
        that C{runUntilCurrent} notices the reactor should stop.
        """
        posixbase.PosixReactorBase.stop(self)
        self.wakeUp()

    def crash(self):
        posixbase.PosixReactorBase.crash(self)
        self.wakeUp()

    def run(self, installSignalHandlers=True):
        q = Queue()
        self.interleave(q.put, installSignalHandlers=installSignalHandlers)
        while self.running:
            try:
                q.get()()
            except StopIteration:
                break


def install():
    """Configure the twisted mainloop to be run using the select() reactor."""
    reactor = ThreadedSelectReactor()
    from twisted.internet.main import installReactor

    installReactor(reactor)
    return reactor


__all__ = ["install"]
