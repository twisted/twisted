
"""

"""

from zope.interface import implementer, Interface

from functools import partial
from collections import deque

class AlreadyQuit(Exception):
    """
    This worker worker is dead and cannot execute more instructions.
    """


_stop = object()


class IWorker(Interface):
    """
    
    """

    def do(task):
        """
        
        """


    def quit():
        """
        
        """


class _Quit(object):
    """
    
    """

    def __init__(self):
        """
        
        """
        self._hasQuit = False


    def __bool__(self):
        """
        
        """
        return self._hasQuit


    def set(self):
        """
        
        """
        self.check()
        self._hasQuit = True


    def check(self):
        """
        
        """
        if self:
            raise AlreadyQuit()



@implementer(IWorker)
class ThreadWorker(object):
    """
    
    """

    def __init__(self, createThread, createQueue):
        """
        
        """
        self._q = createQueue()
        def work():
            for task in iter(self._q.get, _stop):
                task()
        self._thread = createThread(work)
        self._thread.start()
        self._hasQuit = _Quit()


    def do(self, task):
        """
        
        """
        self._hasQuit.check()
        self._q.put(task)


    def quit(self):
        """
        
        """
        # Reject all future work.  Set this _before_ enqueueing _stop, so
        # that no work is ever enqueued _after_ _stop.
        self._hasQuit.set()
        self._q.put(_stop)
        self._thread.join()



def _tell(worker, *args, **kwargs):
    """
    
    """
    def decorate(f):
        worker.do(partial(f, *args, **kwargs))
        return f
    return decorate



@implementer(IWorker)
class Workforce(object):
    """
    
    """

    def __init__(self, createCoordinator, createWorker, logException):
        """
        
        """
        self._hasQuit = False
        self._coordinator = createCoordinator()
        self._createWorker = createWorker
        self._logException = logException

        # Don't touch these except from the coordinator.
        self._idle = set()
        self._pending = deque()


    def grow(self, n):
        """
        
        """
        self._hasQuit.check()
        @_tell(self._coordinator)
        def createOneWorker():
            for x in range(n):
                worker = self._createWorker()
                if worker is None:
                    return
                self._idle.append(worker)


    def shrink(self, n):
        """
        
        """
        self._hasQuit.check()
        self._coordinator.do(partial(self._quitIdlers, n))


    def _quitIdlers(self, n=None):
        """
        
        """
        if n is None:
            n = len(self._idle)
        for x in range(n):
        toQuit, self._idle = self._idle[:n], self._idle[n:]
        for idleWorker in toQuit:
            idleWorker.quit()


    def do(self, task):
        """
        
        """
        self._hasQuit.check()
        self._coordinator.do(partial(self._doInCoordinator, task))


    def _doInCoordinator(self, task):
        """
        
        """
        worker = (self._idle.pop() if self._idle
                  else self._createWorker())
        if worker is None:
            # createWorker may return None if we're out of resources to
            # create workers.
            self._pending.append(task)
            return
        @_tell(worker)
        def doWork():
            try:
                task()
            except:
                self._logException()

            @_tell(self._coordinator)
            def idleAndPending():
                self._idle.add(worker)
                if self._pending:
                    # Re-try the first enqueued thing.
                    # (Explicitly do _not_ honor _hasQuit.)
                    self._doInCoordinator(self._pending.popleft())
                elif self._hasQuit:
                    self._quitIdlers()


    def quit(self):
        """
        
        """
        self._hasQuit.set()
        # In case all the workers are idle when we do this.
        self._coordinator.do(self._quitIdlers)



@implementer(IWorker)
class ReactorWorker(object):
    """
    
    """
    def __init__(self, reactor, quitStops=False):
        """
        
        """
        self._reactor = reactor
        self._hasQuit = _Quit()
        self._quitStops = quitStops


    def do(self, work):
        """
        
        """
        self._hasQuit.check()
        self._reactor.callFromThread(work)


    def quit(self):
        """
        
        """
        self._hasQuit.set()
        if self._quitStops:
            self._reactor.stop()
