"""
twisted.threadpool: an implementation of a threadable Dispatcher.

see the 'threadable' module for more information.
"""

# System Imports
import Queue
import threading
import threadable
import thread
import traceback
import sys
import copy

# Twisted Imports
from twisted.python import worker

class error(Exception):
    pass

WorkerStop = None

class Dispatcher:
    """
    This class (hopefully) generalizes the functionality of a pool of
    threads to which work can be dispatched.
    """
    __inited = 0
    synchronized = ['startSomeWorkers',
                    'stop']
    
    def __init__(self, minthreads=5, maxthreads=20, qlen=1000):
        assert minthreads <= maxthreads, 'minimum is greater than maximum'
        self.q = Queue.Queue(qlen)
        self.max = maxthreads
        self.waiters = []
        self.threads = []
        self.working = {}
        self.owners = {}
        self.workers = 0
        self.joined = 0
        self.osDispatcher = worker.Dispatcher()

    def startSomeWorkers(self):
        if not self.waiters:
            if self.workers < self.max:
                self.workers=self.workers+1
                threading.Thread(target=self.worker).start()

    def dispatchOS(self, owner, func, *args, **kw):
        """
        Dispatch to perform an OS task (currently forking; this may
        require refactoring.
        """
        return apply(self.osDispatcher.dispatch,
                     (owner, func)+args, kw)
    
    def dispatch(self, owner, func, *args, **kw):
        if self.joined: return
        o=(owner,func,args,kw)
        self.startSomeWorkers()
        self.q.put(o)

        
    def withThisOwned(self, owner, func, *args, **kw):
        self.own(owner)
        try:
            return apply(func,args,kw)
        finally:
            self.disown(owner)


    def work(self):
        """
        Process OS dispatches (i.e. those which must be handled in the
        main thread.)
        """
        return self.osDispatcher.work()
        


    def worker(self):
        ct = threading.currentThread()
        self.threads.append(ct)
        self.owners[thread.get_ident()] = []
        while 1:
            self.waiters.append(ct)
            o = self.q.get()
            self.waiters.remove(ct)
            if o == WorkerStop: break
            self.working[ct] = ct
            owner = o[0]
            self.own(owner)
            try:
                apply(apply,o[1:])
            except:
                e = sys.exc_info()[1]
                # breaking encapsulation here... not sure if the
                # 'Exception' protocol supports a way to do this
                # already.  this is for gloop remote tracebacks.
                if hasattr(e, 'traceback'):
                    print e.traceback
                traceback.print_exc(file=sys.stdout)
            self.disown(owner)
            del self.working[ct]
        self.threads.remove(ct)
        self.workers = self.workers-1
        del self.owners[thread.get_ident()] 


    def own(self, owner):
        if owner is not None:
            i = thread.get_ident()
            owners = self.owners.get(i,[])
            owners.append(owner)
            self.owners[i] = owners

        
    def disown(self, owner):
        if owner is not None:
            i = thread.get_ident()
            owners = self.owners[i]
            x = owners.pop()
            assert x is owner, "Inappropriate Owner for Threaded Dispatcher"
        

    def owner(self):
        # This returns the currently "active" object (the one
        # responsible for the work currently being performed, in this
        # thread, by this dispatcher).  This can be used for things
        # such as logging.
        
        i = thread.get_ident()
        try:
            return self.owners[i][-1]
        except:
            return self.defaultOwner
    
    
    def stop(self):
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


threadable.synchronize(Dispatcher)
