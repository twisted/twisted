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
from __future__ import annotations

from errno import EBADF, EINTR
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable

from zope.interface import implementer

from twisted._threads import ThreadWorker
from twisted.internet import posixbase
from twisted.internet.interfaces import IReactorFDSet, IReadDescriptor, IWriteDescriptor
from twisted.internet.posixbase import _NO_FILEDESC
from twisted.internet.selectreactor import _preenDescriptors, _select
from twisted.logger import Logger
from twisted.python.log import callWithLogger as _callWithLogger

_log = Logger()


def raiseException(e):
    raise e


def _threadsafeSelect(
    timeout: float | None,
    readmap: dict[int, IReadDescriptor],
    writemap: dict[int, IWriteDescriptor],
    handleResult: Callable[
        [
            list[int],
            list[int],
            dict[int, IReadDescriptor],
            dict[int, IWriteDescriptor],
            bool,
        ],
        None,
    ],
) -> None:
    """
    Invoke C{select}.  This will be called in a non-main thread, so it is very
    careful to work only on integers and avoid calling any application code.
    """
    preen = False
    r = []
    w = []
    while 1:
        readints = readmap.keys()
        writeints = writemap.keys()
        try:
            result = _select(readints, writeints, [], timeout)
        except ValueError:
            # Possible problems with file descriptors that were passed:
            # ValueError may indicate that a file descriptor has gone negative,
            preen = True
            break
        except TypeError:
            # and TypeError indicates that something *totally* invalid (an
            # object without a .fileno method, or such a method with a result
            # that has a type other than `int`) was passed.  This is probably a
            # bug in application code that we *can* recover from, so we will
            # log it and try to do that.
            _log.failure("while calling select() in a thread")
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
    handleResult(r, w, readmap, writemap, preen)


def _noWaker(work: Callable[[], None]) -> None:
    raise RuntimeError("threaded select reactor not interleaved")


@implementer(IReactorFDSet)
class ThreadedSelectReactor(posixbase.PosixReactorBase):
    """A threaded select() based reactor - runs on all POSIX platforms and on
    Win32.
    """

    def __init__(self, waker: Callable[[Callable[[], None]], None] = _noWaker) -> None:
        self.reads: set[IReadDescriptor] = set()
        self.writes: set[IWriteDescriptor] = set()
        posixbase.PosixReactorBase.__init__(self)
        self._selectorThread: ThreadWorker | None = None
        self.mainWaker = waker
        self._iterationQueue: Queue[Callable[[], None]] | None = None

    def wakeUp(self):
        # we want to wake up from any thread
        self.waker.wakeUp()

    def callLater(self, *args, **kw):
        tple = posixbase.PosixReactorBase.callLater(self, *args, **kw)
        self.wakeUp()
        return tple

    def _mapOneEntry(self, selectable: Any) -> int | None:
        with _log.handlingFailures("determining fileno for selectability"):
            fd: int = selectable.fileno()
            return fd
        return None  # type:ignore[unreachable]

    def _doReadOrWrite(self, selectable, method):
        with _log.handlingFailures(
            "while handling selectable {sel}", sel=selectable
        ) as op:
            why = getattr(selectable, method)()
        if op.failed:
            why = op.failure.value
        if why:
            self._disconnectSelectable(selectable, why, method == "doRead")

    def _selectOnce(self, timeout: float | None) -> None:
        reads: dict[int, Any] = {}
        writes: dict[int, Any] = {}
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

        def callReadsAndWrites(
            r: list[int],
            w: list[int],
            readmap: dict[int, IReadDescriptor],
            writemap: dict[int, IWriteDescriptor],
            preen: bool,
        ) -> None:
            @self.mainWaker
            def onMainThread() -> None:
                if preen:
                    _preenDescriptors(
                        self.reads, self.writes, self._disconnectSelectable
                    )
                    return
                _drdw = self._doReadOrWrite

                for readable in r:
                    rselectable = readmap[readable]
                    if rselectable in self.reads:
                        _callWithLogger(rselectable, _drdw, rselectable, "doRead")

                for writable in w:
                    wselectable = writemap[writable]
                    if wselectable in self.writes:
                        _callWithLogger(wselectable, _drdw, wselectable, "doWrite")

                self.runUntilCurrent()
                if self._started:
                    self._selectOnce(self.timeout())
                else:
                    self._cleanUpThread()

        if self._selectorThread is None:
            self._selectorThread = ThreadWorker(
                lambda target: Thread(target=target).start(), Queue()
            )
        self._selectorThread.do(
            lambda: _threadsafeSelect(timeout, reads, writes, callReadsAndWrites)
        )

    def _cleanUpThread(self) -> None:
        """
        Ensure that the selector thread is stopped.
        """
        oldThread, self._selectorThread = self._selectorThread, None
        if oldThread is not None:
            oldThread.quit()

    def interleave(
        self,
        waker: Callable[[Callable[[], None]], None],
        installSignalHandlers: bool = True,
    ) -> None:
        """
        interleave(waker) interleaves this reactor with the current application
        by moving the blocking parts of the reactor (select() in this case) to
        a separate thread.  This is typically useful for integration with GUI
        applications which have their own event loop already running.

        See the module docstring for more information.
        """
        self.mainWaker = waker
        self.startRunning(installSignalHandlers)
        self._selectOnce(0.0)

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

    # The following methods are mostly for test-suite support, to make
    # ThreadedSelectReactor behave like another reactor you might call run()
    # on.
    def _testMainLoopSetup(self) -> None:
        """
        Mostly for compliance with L{IReactorCore} and usability with the
        tests, set up a fake blocking main-loop; make the "foreign" main loop
        we are interfacing with be C{self.mainLoop()}, that is reading from a
        basic Queue.
        """
        self._iterationQueue = Queue()
        self.mainWaker = self._iterationQueue.put
        self._selectOnce(0.0)

    def _uninstallHandler(self) -> None:
        """
        Handle uninstallation to ensure that cleanup is properly performed by
        ReactorBuilder tests.
        """
        super()._uninstallHandler()
        self._cleanUpThread()

    def iterate(self, timeout: float = 0.0) -> None:
        if self._iterationQueue is None and self.mainWaker is _noWaker:
            self._testMainLoopSetup()
        self.wakeUp()
        super().iterate(timeout)

    def doIteration(self, timeout: float | None) -> None:
        assert self._iterationQueue is not None
        try:
            work = self._iterationQueue.get(timeout=timeout)
        except Empty:
            return
        work()

    def mainLoop(self) -> None:
        """
        This should not normally be run.
        """
        self._testMainLoopSetup()
        super().mainLoop()


def install():
    """Configure the twisted mainloop to be run using the select() reactor."""
    reactor = ThreadedSelectReactor()
    from twisted.internet.main import installReactor

    installReactor(reactor)
    return reactor


__all__ = ["install"]
