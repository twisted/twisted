# -*- test-case-name: twisted.test.test_threadpool -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
twisted.threadpool: a pool of threads to which we dispatch tasks.

In most cases you can just use reactor.callInThread and friends
instead of creating a thread pool directly.
"""

# System Imports
import Queue
import threading
import threadable
import copy
import sys

# Twisted Imports
from twisted.python import log, runtime, context
class WorkerStop:
    pass
WorkerStop = WorkerStop()

# initialize threading
threadable.init(1)


class ThreadPool:
    """
    This class (hopefully) generalizes the functionality of a pool of
    threads to which work can be dispatched.

    dispatch(), dispatchWithCallback() and stop() should only be called from
    a single thread, unless you make a subclass where stop() and
    _startSomeWorkers() are synchronized.
    """
    __inited = 0
    min = 5
    max = 20
    joined = 0
    started = 0
    workers = 0
    name = None

    def __init__(self, minthreads=5, maxthreads=20, name=None):
        """Create a new threadpool.

        @param minthreads: minimum number of threads in the pool

        @param maxthreads: maximum number of threads in the pool
        """
        assert minthreads >= 0, 'minimum is negative'
        assert minthreads <= maxthreads, 'minimum is greater than maximum'
        self.q = Queue.Queue(0)
        self.min = minthreads
        self.max = maxthreads
        self.name = name
        if runtime.platform.getType() != "java":
            self.waiters = []
            self.threads = []
            self.working = []
        else:
            self.waiters = ThreadSafeList()
            self.threads = ThreadSafeList()
            self.working = ThreadSafeList()

    def start(self):
        """Start the threadpool.
        """
        self.joined = 0
        self.started = 1
        # Start some threads.
        self.adjustPoolsize()

    def startAWorker(self):
        self.workers = self.workers + 1
        name = "PoolThread-%s-%s" % (self.name or id(self), self.workers)
        try:
            firstJob = self.q.get(0)
        except Queue.Empty:
            firstJob = None
        newThread = threading.Thread(target=self._worker, name=name, args=(firstJob,))
        self.threads.append(newThread)
        newThread.start()

    def stopAWorker(self):
        self.q.put(WorkerStop)
        self.workers = self.workers-1

    def __setstate__(self, state):
        self.__dict__ = state
        ThreadPool.__init__(self, self.min, self.max)

    def __getstate__(self):
        state = {}
        state['min'] = self.min
        state['max'] = self.max
        return state

    def _startSomeWorkers(self):
        while (
            self.workers < self.max and # Don't create too many
            len(self.waiters) < self.q.qsize() # but create enough
            ):
            self.startAWorker()

    def dispatch(self, owner, func, *args, **kw):
        """Dispatch a function to be a run in a thread.
        """
        self.callInThread(func,*args,**kw)

    def callInThread(self, func, *args, **kw):
        if self.joined:
            return
        ctx = context.theContextTracker.currentContext().contexts[-1]
        o = (ctx, func, args, kw)
        self.q.put(o)
        if self.started:
            self._startSomeWorkers()

    def _runWithCallback(self, callback, errback, func, args, kwargs):
        try:
            result = apply(func, args, kwargs)
        except:
            errback(sys.exc_info()[1])
        else:
            callback(result)

    def dispatchWithCallback(self, owner, callback, errback, func, *args, **kw):
        """Dispatch a function, returning the result to a callback function.

        The callback function will be called in the thread - make sure it is
        thread-safe.
        """
        self.callInThread(self._runWithCallback, callback, errback, func, args, kw)

    def _worker(self, o):
        ct = threading.currentThread()
        while 1:
            if o is WorkerStop:
                break
            elif o is not None:
                self.working.append(ct)
                ctx, function, args, kwargs = o
                try:
                    context.call(ctx, function, *args, **kwargs)
                except:
                    context.call(ctx, log.deferr)
                self.working.remove(ct)
                del o, ctx, function, args, kwargs
            self.waiters.append(ct)
            o = self.q.get()
            self.waiters.remove(ct)

        self.threads.remove(ct)

    def stop(self):
        """Shutdown the threads in the threadpool."""
        self.joined = 1
        threads = copy.copy(self.threads)
        for thread in range(self.workers):
            self.q.put(WorkerStop)
            self.workers = self.workers-1

        # and let's just make sure
        # FIXME: threads that have died before calling stop() are not joined.
        for thread in threads:
            thread.join()

    def adjustPoolsize(self, minthreads=None, maxthreads=None):
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
        log.msg('queue: %s'   % self.q.queue)
        log.msg('waiters: %s' % self.waiters)
        log.msg('workers: %s' % self.working)
        log.msg('total: %s'   % self.threads)


class ThreadSafeList:
    """In Jython 2.1 lists aren't thread-safe, so this wraps it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.l = []

    def append(self, i):
        self.lock.acquire()
        try:
            self.l.append(i)
        finally:
            self.lock.release()

    def remove(self, i):
        self.lock.acquire()
        try:
            self.l.remove(i)
        finally:
            self.lock.release()

    def __len__(self):
        return len(self.l)
