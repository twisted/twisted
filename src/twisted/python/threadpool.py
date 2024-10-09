# -*- test-case-name: twisted.test.test_threadpool -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
twisted.python.threadpool: a pool of threads to which we dispatch tasks.

In most cases you can just use C{reactor.callInThread} and friends
instead of creating a thread pool directly.
"""

from __future__ import annotations

from threading import Thread, current_thread
from typing import Any, Callable, List, Optional, TypeVar

from typing_extensions import ParamSpec, Protocol, TypedDict

from twisted._threads import pool as _pool
from twisted.python import context, log
from twisted.python.deprecate import deprecated
from twisted.python.failure import Failure
from twisted.python.versions import Version

_P = ParamSpec("_P")
_R = TypeVar("_R")


class _SupportsQsize(Protocol):
    def qsize(self) -> int:
        ...


class _State(TypedDict):
    min: int
    max: int


WorkerStop = object()


class ThreadPool:
    """
    This class (hopefully) generalizes the functionality of a pool of threads
    to which work can be dispatched.

    L{callInThread} and L{stop} should only be called from a single thread.

    @ivar started: Whether or not the thread pool is currently running.
    @type started: L{bool}

    @ivar threads: List of workers currently running in this thread pool.
    @type threads: L{list}

    @ivar _pool: A hook for testing.
    @type _pool: callable compatible with L{_pool}
    """

    min = 5
    max = 20
    joined = False
    started = False
    name = None

    threadFactory = Thread
    currentThread = staticmethod(
        deprecated(
            version=Version("Twisted", 22, 1, 0),
            replacement="threading.current_thread",
        )(current_thread)
    )
    _pool = staticmethod(_pool)

    def __init__(
        self, minthreads: int = 5, maxthreads: int = 20, name: Optional[str] = None
    ):
        """
        Create a new threadpool.

        @param minthreads: minimum number of threads in the pool
        @type minthreads: L{int}

        @param maxthreads: maximum number of threads in the pool
        @type maxthreads: L{int}

        @param name: The name to give this threadpool; visible in log messages.
        @type name: native L{str}
        """
        assert minthreads >= 0, "minimum is negative"
        assert minthreads <= maxthreads, "minimum is greater than maximum"
        self.min = minthreads
        self.max = maxthreads
        self.name = name
        self.threads: List[Thread] = []

        def trackingThreadFactory(*a: Any, **kw: Any) -> Thread:
            thread = self.threadFactory(  # type: ignore[misc]
                *a, name=self._generateName(), **kw
            )
            self.threads.append(thread)
            return thread

        def currentLimit() -> int:
            if not self.started:
                return 0
            return self.max

        self._team = self._pool(currentLimit, trackingThreadFactory)

    @property
    def workers(self) -> int:
        """
        For legacy compatibility purposes, return a total number of workers.

        @return: the current number of workers, both idle and busy (but not
            those that have been quit by L{ThreadPool.adjustPoolsize})
        @rtype: L{int}
        """
        stats = self._team.statistics()
        return stats.idleWorkerCount + stats.busyWorkerCount

    @property
    def working(self) -> list[None]:
        """
        For legacy compatibility purposes, return the number of busy workers as
        expressed by a list the length of that number.

        @return: the number of workers currently processing a work item.
        @rtype: L{list} of L{None}
        """
        return [None] * self._team.statistics().busyWorkerCount

    @property
    def waiters(self) -> list[None]:
        """
        For legacy compatibility purposes, return the number of idle workers as
        expressed by a list the length of that number.

        @return: the number of workers currently alive (with an allocated
            thread) but waiting for new work.
        @rtype: L{list} of L{None}
        """
        return [None] * self._team.statistics().idleWorkerCount

    @property
    def _queue(self) -> _SupportsQsize:
        """
        For legacy compatibility purposes, return an object with a C{qsize}
        method that indicates the amount of work not yet allocated to a worker.

        @return: an object with a C{qsize} method.
        """

        class NotAQueue:
            def qsize(q) -> int:
                """
                Pretend to be a Python threading Queue and return the
                number of as-yet-unconsumed tasks.

                @return: the amount of backlogged work not yet dispatched to a
                    worker.
                @rtype: L{int}
                """
                return self._team.statistics().backloggedWorkCount

        return NotAQueue()

    q = _queue  # Yes, twistedchecker, I want a single-letter
    # attribute name.

    def start(self) -> None:
        """
        Start the threadpool.
        """
        self.joined = False
        self.started = True
        # Start some threads.
        self.adjustPoolsize()
        backlog = self._team.statistics().backloggedWorkCount
        if backlog:
            self._team.grow(backlog)

    def startAWorker(self) -> None:
        """
        Increase the number of available workers for the thread pool by 1, up
        to the maximum allowed by L{ThreadPool.max}.
        """
        self._team.grow(1)

    def _generateName(self) -> str:
        """
        Generate a name for a new pool thread.

        @return: A distinctive name for the thread.
        @rtype: native L{str}
        """
        return f"PoolThread-{self.name or id(self)}-{self.workers}"

    def stopAWorker(self) -> None:
        """
        Decrease the number of available workers by 1, by quitting one as soon
        as it's idle.
        """
        self._team.shrink(1)

    def __setstate__(self, state: _State) -> None:
        setattr(self, "__dict__", state)
        ThreadPool.__init__(self, self.min, self.max)

    def __getstate__(self) -> _State:
        return _State(min=self.min, max=self.max)

    def callInThread(
        self, func: Callable[_P, object], *args: _P.args, **kw: _P.kwargs
    ) -> None:
        """
        Call a callable object in a separate thread.

        @param func: callable object to be called in separate thread

        @param args: positional arguments to be passed to C{func}

        @param kw: keyword args to be passed to C{func}
        """
        self.callInThreadWithCallback(None, func, *args, **kw)

    def callInThreadWithCallback(
        self,
        onResult: Optional[Callable[[bool, _R], object]],
        func: Callable[_P, _R],
        *args: _P.args,
        **kw: _P.kwargs,
    ) -> None:
        """
        Call a callable object in a separate thread and call C{onResult} with
        the return value, or a L{twisted.python.failure.Failure} if the
        callable raises an exception.

        The callable is allowed to block, but the C{onResult} function must not
        block and should perform as little work as possible.

        A typical action for C{onResult} for a threadpool used with a Twisted
        reactor would be to schedule a L{twisted.internet.defer.Deferred} to
        fire in the main reactor thread using C{.callFromThread}.  Note that
        C{onResult} is called inside the separate thread, not inside the
        reactor thread.

        @param onResult: a callable with the signature C{(success, result)}.
            If the callable returns normally, C{onResult} is called with
            C{(True, result)} where C{result} is the return value of the
            callable.  If the callable throws an exception, C{onResult} is
            called with C{(False, failure)}.

            Optionally, C{onResult} may be L{None}, in which case it is not
            called at all.

        @param func: callable object to be called in separate thread

        @param args: positional arguments to be passed to C{func}

        @param kw: keyword arguments to be passed to C{func}
        """
        if self.joined:
            return
        ctx = context.theContextTracker.currentContext().contexts[-1]

        def inContext() -> None:
            try:
                result = inContext.theWork()  # type: ignore[attr-defined]
                ok = True
            except BaseException:
                result = Failure()
                ok = False

            inContext.theWork = None  # type: ignore[attr-defined]
            if inContext.onResult is not None:  # type: ignore[attr-defined]
                inContext.onResult(ok, result)  # type: ignore[attr-defined]
                inContext.onResult = None  # type: ignore[attr-defined]
            elif not ok:
                log.err(result)

        # Avoid closing over func, ctx, args, kw so that we can carefully
        # manage their lifecycle.  See
        # test_threadCreationArgumentsCallInThreadWithCallback.
        inContext.theWork = lambda: context.call(  # type: ignore[attr-defined]
            ctx,
            func,
            *args,
            **kw,
        )
        inContext.onResult = onResult  # type: ignore[attr-defined]

        self._team.do(inContext)

    def stop(self) -> None:
        """
        Shutdown the threads in the threadpool.
        """
        self.joined = True
        self.started = False
        self._team.quit()
        for thread in self.threads:
            thread.join()

    def adjustPoolsize(
        self, minthreads: Optional[int] = None, maxthreads: Optional[int] = None
    ) -> None:
        """
        Adjust the number of available threads by setting C{min} and C{max} to
        new values.

        @param minthreads: The new value for L{ThreadPool.min}.

        @param maxthreads: The new value for L{ThreadPool.max}.
        """
        if minthreads is None:
            minthreads = self.min
        if maxthreads is None:
            maxthreads = self.max

        assert minthreads >= 0, "minimum is negative"
        assert minthreads <= maxthreads, "minimum is greater than maximum"

        self.min = minthreads
        self.max = maxthreads
        if not self.started:
            return

        # Kill of some threads if we have too many.
        if self.workers > self.max:
            self._team.shrink(self.workers - self.max)
        # Start some threads if we have too few.
        if self.workers < self.min:
            self._team.grow(self.min - self.workers)

    def dumpStats(self) -> None:
        """
        Dump some plain-text informational messages to the log about the state
        of this L{ThreadPool}.
        """
        log.msg(f"waiters: {self.waiters}")
        log.msg(f"workers: {self.working}")
        log.msg(f"total: {self.threads}")
