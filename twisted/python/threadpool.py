# -*- test-case-name: twisted.test.test_threadpool -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An implementation of a pool of threads to which we dispatch tasks with.

In most cases you can just use C{reactor.callInThread} and friends instead of
creating a thread pool directly.
"""

from __future__ import division, absolute_import

try:
    from Queue import Queue
except ImportError:
    from queue import Queue
import contextlib
import copy
import threading

from twisted.python import log, context, failure


WorkerStop = object()


class ThreadPool(object):
    """
    Generalizes the functionality of a pool of threads to which work can be
    dispatched.

    L{callInThread} and L{stop} should only be called from a single thread,
    unless you make a subclass where L{stop} and L{_startSomeWorkers} are
    synchronized.

    @ivar q: Queue of tasks to run.
    @type q: L{Queue}
    @ivar started: Whether or not the thread pool is currently running.
    @type started: L{bool}
    @ivar joined: The inverse of L{ThreadPool.started}.
    @type joined: L{bool}
    @ivar workers: Number of workers currently running in this thread pool.
    @type workers: L{int}
    @ivar waiters: Number of workers currently waiting in this thread pool.
    @type waiters: L{int}
    @ivar threads: List of threads currently running in this thread pool.
    @type threads: L{list}
    @ivar min: Minimum amount of running threads allowed in the pool.
    @type min: L{int}
    @ivar max: Maximum amount of running threads allowed in the pool.
    @type max: L{int}
    @ivar name: Name used to identify the thread pool.
    @type name: L{bytes} or L{NoneType <types.NoneType>}
    """
    min = 5
    max = 20
    joined = False
    started = False
    workers = 0
    name = None

    threadFactory = threading.Thread
    currentThread = staticmethod(threading.currentThread)

    def __init__(self, minthreads=5, maxthreads=20, name=None):
        """
        Create a new L{ThreadPool}.

        @param minthreads: Minimum number of threads allowed in the pool.
        @type minthreads: L{int}
        @param maxthreads: Maximum number of threads allowed in the pool.
        @type maxthreads: L{int}
        @param name: Name used to identify the thread pool.
        @type name: L{bytes} or L{NoneType <types.NoneType>}
        """
        assert minthreads >= 0, 'minimum is negative'
        assert minthreads <= maxthreads, 'minimum is greater than maximum'
        self.q = Queue(0)
        self.min = minthreads
        self.max = maxthreads
        self.name = name
        self.waiters = []
        self.threads = []
        self.working = []


    def start(self):
        """
        Start the threadpool.
        """
        self.joined = False
        self.started = True
        # Start some threads.
        self.adjustPoolsize()


    def startAWorker(self):
        """
        Start a new worker.
        """
        self.workers += 1
        name = "PoolThread-%s-%s" % (self.name or id(self), self.workers)
        newThread = self.threadFactory(target=self._worker, name=name)
        self.threads.append(newThread)
        newThread.start()


    def stopAWorker(self):
        """
        Stop the next worker that is finished.
        """
        self.q.put(WorkerStop)
        self.workers -= 1


    def __setstate__(self, state):
        self.__dict__ = state
        ThreadPool.__init__(self, self.min, self.max)


    def __getstate__(self):
        state = {}
        state['min'] = self.min
        state['max'] = self.max
        return state


    def _startSomeWorkers(self):
        """
        Start enough workers to handle the current queue, but no more than
        L{ThreadPool.max}.
        """
        neededSize = self.q.qsize() + len(self.working)
        # Create enough, but not too many
        while self.workers < min(self.max, neededSize):
            self.startAWorker()


    def callInThread(self, func, *args, **kw):
        """
        Call a callable object in a separate thread.

        @param func: callable object to be called in separate thread
        @param args: positional arguments to be passed to C{func}
        @param kw: keyword args to be passed to C{func}
        """
        self.callInThreadWithCallback(None, func, *args, **kw)


    def callInThreadWithCallback(self, onResult, func, *args, **kw):
        """
        Call a callable object in a separate thread and call C{onResult} with
        the return value, or a L{twisted.python.failure.Failure} if the
        callable raises an exception.

        The callable is allowed to block, but the C{onResult} function must not
        block and should perform as little work as possible.

        A typical action for C{onResult} for a threadpool used with a Twisted
        reactor would be to schedule a L{twisted.internet.defer.Deferred} to
        fire in the main reactor thread using C{.callFromThread}. Note that
        C{onResult} is called inside the separate thread, not inside the
        reactor thread.

        @param onResult: a callable with the signature C{(success, result)}.
            If the callable returns normally, C{onResult} is called with
            C{(True, result)} where C{result} is the return value of the
            callable. If the callable throws an exception, C{onResult} is
            called with C{(False, failure)}.

            Optionally, C{onResult} may be L{NoneType <types.NoneType>}, in
            which case it is not called at all.
        @param func: callable object to be called in separate thread.
        @param args: positional arguments to be passed to C{func}.
        @param kw: keyword arguments to be passed to C{func}.
        """
        if self.joined:
            return
        ctx = context.theContextTracker.currentContext().contexts[-1]
        o = (ctx, func, args, kw, onResult)
        self.q.put(o)
        if self.started:
            self._startSomeWorkers()


    @contextlib.contextmanager
    def _workerState(self, stateList, workerThread):
        """
        Manages adding and removing this worker from a list of workers in a
        particular state.

        @param stateList: the list managing workers in this state.
        @param workerThread: the thread the worker is running in, used to
            represent the worker in stateList.
        """
        stateList.append(workerThread)
        try:
            yield
        finally:
            stateList.remove(workerThread)


    def _worker(self):
        """
        Method used as target of the created threads: retrieve a task to run
        from the threadpool, run it, and proceed to the next task until
        threadpool is stopped.
        """
        ct = self.currentThread()
        o = self.q.get()
        while o is not WorkerStop:
            with self._workerState(self.working, ct):
                ctx, function, args, kwargs, onResult = o
                del o

                try:
                    result = context.call(ctx, function, *args, **kwargs)
                    success = True
                except:
                    success = False
                    if onResult is None:
                        context.call(ctx, log.err)
                        result = None
                    else:
                        result = failure.Failure()

                del function, args, kwargs

            if onResult is not None:
                try:
                    context.call(ctx, onResult, success, result)
                except:
                    context.call(ctx, log.err)

            del ctx, onResult, result

            with self._workerState(self.waiters, ct):
                o = self.q.get()

        self.threads.remove(ct)


    def stop(self):
        """
        Stop all the threads in the threadpool.

        If threads are still working, this will be blocking.
        """
        self.joined = True
        self.started = False
        threads = copy.copy(self.threads)
        while self.workers:
            self.q.put(WorkerStop)
            self.workers -= 1

        # And let's just make sure
        # FIXME: threads that have died before calling stop() are not joined.
        for thread in threads:
            thread.join()


    def adjustPoolsize(self, minthreads=None, maxthreads=None):
        """
        Adjust the pool size, starting or stopping workers if required.

        @param minthreads: Minimum number of threads allowed in the pool.
        @type minthreads: L{int}
        @param maxthreads: Maximum number of threads allowed in the pool.
        @type maxthreads: L{int}
        """
        if minthreads is None:
            minthreads = self.min
        if maxthreads is None:
            maxthreads = self.max

        assert minthreads >= 0, 'minimum is negative'
        assert minthreads <= maxthreads, 'minimum is greater than maximum'

        self.min = minthreads
        self.max = maxthreads
        if not self.started:
            return

        # Kill of some threads if we have too many.
        while self.workers > self.max:
            self.stopAWorker()
        # Start some threads if we have too few.
        while self.workers < self.min:
            self.startAWorker()
        # Start some threads if there is a need.
        self._startSomeWorkers()


    def dumpStats(self):
        """
        Dump some statistics about the current queue, workers and threads.
        """
        log.msg('queue: %s' % (self.q.queue,))
        log.msg('waiters: %s' % (self.waiters,))
        log.msg('workers: %s' % (self.working,))
        log.msg('total: %s' % (self.threads,))
