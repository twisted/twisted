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
import sys
import copy

# Twisted Imports
from twisted.python import log

class error(Exception):
    pass

WorkerStop = None


class ThreadPool:
    """
    This class (hopefully) generalizes the functionality of a pool of
    threads to which work can be dispatched.
    """
    __inited = 0
    synchronized = ['_startSomeWorkers', 'stop']
    
    def __init__(self, minthreads=5, maxthreads=20, qlen=1000):
        assert minthreads <= maxthreads, 'minimum is greater than maximum'
        self.q = Queue.Queue(qlen)
        self.max = maxthreads
        self.waiters = []
        self.threads = []
        self.working = {}
        self.workers = 0
        self.joined = 0

    def _startSomeWorkers(self):
        if not self.waiters:
            if self.workers < self.max:
                self.workers=self.workers+1
                threading.Thread(target=self._worker).start()

    def dispatch(self, owner, func, *args, **kw):
        """Dispatch a function to be a run in a thread.
        
        owner must be a loggable object.
        """
        assert isinstance(owner, log.Logger), "owner isn't logger"
        if self.joined: return
        o=(owner,func,args,kw)
        self._startSomeWorkers()
        self.q.put(o)
    
    def _runWithCallback(self, callback, errback, func, args, kwargs):
        try:
            result = apply(func, args, kwargs)
        except Exception, e:
            errback(e)
        else:
            callback(result)
    
    def dispatchWithCallback(self, owner, callback, errback, func, *args, **kw):
        """Dispatch a function, returning the result to a callback function.
        
        The callback function will be called in the thread - make sure it is
        thread-safe."""
        self.dispatch(owner, self._runWithCallback, callback, errback, func, args, kw)

    def _worker(self):
        ct = threading.currentThread()
        self.threads.append(ct)
        
        while 1:
            self.waiters.append(ct)
            o = self.q.get()
            self.waiters.remove(ct)
            if o == WorkerStop: break
            self.working[ct] = ct
            owner, function, args, kwargs = o
            log.logOwner.own(owner)
            try:
                apply(function, args, kwargs)
            except:
                log.msg('Thread raised an exception.')
                traceback.print_exc(file=log.logfile)
            log.logOwner.disown(owner)
            del self.working[ct]
        self.threads.remove(ct)
        self.workers = self.workers-1
    
    def stop(self):
        """Shutdown the threads in the threadpool."""
        self.dumpStats()
        self.joined=1
        threads = copy.copy(self.threads)
        for thread in range(self.workers):
            self.q.put(WorkerStop)

        # and let's just make sure
        for thread in threads:
            thread.join()
    
    def dumpStats(self):
        print 'queue:',self.q.queue
        print 'waiters:',self.waiters
        print 'workers:',self.working
        print 'total:',self.threads


threadable.synchronize(ThreadPool)
