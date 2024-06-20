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
            # ValueError may indicate that a file descriptor has gone negative.
            preen = True
            break
        except OSError as se:
            # The select() system call encountered an error.
            if se.args[0] == EINTR:
                # EINTR is hard to replicate in tests using an actual select(),
                # and I don't want to dedicate effort to testing this function
                # when it needs to be refactored with selectreactor.

                return  # pragma: no cover
            elif se.args[0] == EBADF:
                preen = True
                break
            else:
                # OK, I really don't know what's going on.  Blow up.  Never
                # mind with the coverage here, since we are just trying to make
                # sure we don't swallow an exception.
                raise  # pragma: no cover
        else:
            r, w, ignored = result
            break
    handleResult(r, w, readmap, writemap, preen)


@implementer(IReactorFDSet)
class ThreadedSelectReactor(posixbase.PosixReactorBase):
    """A threaded select() based reactor - runs on all POSIX platforms and on
    Win32.
    """

    def __init__(
        self, waker: Callable[[Callable[[], None]], None] | None = None
    ) -> None:
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

    def _doReadOrWrite(self, selectable: object, method: str) -> None:
        with _log.failuresHandled(
            "while handling selectable {sel}", sel=selectable
        ) as op:
            why = getattr(selectable, method)()
        if (fail := op.failure) is not None:
            why = fail.value
        if why:
            self._disconnectSelectable(selectable, why, method == "doRead")

    def _selectOnce(self, timeout: float | None, keepGoing: bool) -> None:
        reads: dict[int, Any] = {}
        writes: dict[int, Any] = {}
        for isRead, fdmap, d in [
            (True, self.reads, reads),
            (False, self.writes, writes),
        ]:
            for each in fdmap:  # type:ignore[attr-defined]
                d[each.fileno()] = each

        mainWaker = self.mainWaker
        assert mainWaker is not None, (
            "neither .interleave() nor .mainLoop() / .run() called, "
            "but we are somehow running the reactor"
        )

        def callReadsAndWrites(
            r: list[int],
            w: list[int],
            readmap: dict[int, IReadDescriptor],
            writemap: dict[int, IWriteDescriptor],
            preen: bool,
        ) -> None:
            @mainWaker
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
                if self._started and keepGoing:
                    # see coverage note in .interleave()
                    self._selectOnce(self.timeout(), True)  # pragma: no cover
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
        # TODO: This method is excluded from coverage because it only happens
        # in the case where we are actually running on a foreign event loop,
        # and twisted's test suite isn't set up that way.  It would be nice to
        # add some dedicated tests for ThreadedSelectReactor that covered this
        # case.
        self.mainWaker = waker  # pragma: no cover
        self.startRunning(installSignalHandlers)  # pragma: no cover
        self._selectOnce(0.0, True)  # pragma: no cover

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

    def _uninstallHandler(self) -> None:
        """
        Handle uninstallation to ensure that cleanup is properly performed by
        ReactorBuilder tests.
        """
        super()._uninstallHandler()
        self._cleanUpThread()

    def iterate(self, timeout: float = 0.0) -> None:
        if self._iterationQueue is None and self.mainWaker is None:  # pragma: no branch
            self._testMainLoopSetup()
        self.wakeUp()
        super().iterate(timeout)

    def doIteration(self, timeout: float | None) -> None:
        assert self._iterationQueue is not None
        self._selectOnce(timeout, False)
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
