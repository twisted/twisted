# -*- test-case-name: twisted.test.test_threadpool -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
twisted.threadpool: a pool of threads to which we dispatch tasks.

If you want integration with Twisted's event loop then use
twisted.internet.threadtask instead.
"""

# System Imports
import Queue
import threading
import threadable
import traceback
import copy
import sys

# Twisted Imports
from twisted.python import log, runtime, context

WorkerStop = None

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
    
    def __init__(self, minthreads=5, maxthreads=20):
        """Create a new threadpool.

        @param minthreads: minimum number of threads in the pool

        @param maxthreads: maximum number of threads in the pool
        """

        assert minthreads <= maxthreads, 'minimum is greater than maximum'
        self.q = Queue.Queue(0)
        self.min = minthreads
        self.max = maxthreads
        if runtime.platform.getType() != "java":
            self.waiters = []
        else:
            self.waiters = ThreadSafeList()
        self.threads = []
        self.working = {}
    
    def start(self):
        """Start the threadpool.
        """
        self.workers = min(max(self.min, self.q.qsize()), self.max)
        self.joined = 0
        self.started = 1
        for i in range(self.workers):
            name = "PoolThread-%s-%s" % (id(self), i)
            threading.Thread(target=self._worker, name=name).start()

    def __setstate__(self, state):
        self.__dict__ = state
        ThreadPool.__init__(self, self.min, self.max)

    def __getstate__(self):
        state = {}
        state['min'] = self.min
        state['max'] = self.max
        return state
    
    def _startSomeWorkers(self):
        if not self.waiters:
            if self.workers < self.max:
                self.workers = self.workers + 1
                name = "PoolThread-%s-%s" % (id(self), self.workers)
                threading.Thread(target=self._worker, name=name).start()

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
        if self.started and not self.waiters:
            self._startSomeWorkers()
    
    def _runWithCallback(self, callback, errback, func, args, kwargs):
        try:
            result = apply(func, args, kwargs)
        except:
            errback(sys.exc_value)
        else:
            callback(result)
    
    def dispatchWithCallback(self, owner, callback, errback, func, *args, **kw):
        """Dispatch a function, returning the result to a callback function.
        
        The callback function will be called in the thread - make sure it is
        thread-safe."""
        self.callInThread(self._runWithCallback, callback, errback, func, args, kw)

    def _worker(self):
        ct = threading.currentThread()
        self.threads.append(ct)
        
        while 1:
            self.waiters.append(ct)
            o = self.q.get()
            self.waiters.remove(ct)
            if o == WorkerStop: break
            self.working[ct] = ct
            ctx, function, args, kwargs = o
            try:
                context.call(ctx, function, *args, **kwargs)
            except:
                context.call(ctx, log.deferr)
            del self.working[ct]
        self.threads.remove(ct)
        self.workers = self.workers-1
    
    def stop(self):
        """Shutdown the threads in the threadpool."""
        self.joined = 1
        threads = copy.copy(self.threads)
        for thread in range(self.workers):
            self.q.put(WorkerStop)

        # and let's just make sure
        for thread in threads:
            thread.join()
    
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
