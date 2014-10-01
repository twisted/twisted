
from collections import deque
from zope.interface import implementer

from . import IWorker
from ._convenience import Quit



class Statistics(object):
    """
    Statistics about a L{Team}'s current activity.

    @ivar idleWorkerCount: The number of idle workers.
    @type idleWorkerCount: L{int}

    @ivar busyWorkerCount: The number of busy workers.
    @type busyWorkerCount: L{int}

    @ivar pendingCount: The number of pending tasks.
    @type pendingCount: L{int}
    """

    def __init__(self, idleWorkerCount, busyWorkerCount, pendingCount):
        """
        Create some statistics.
        """
        self.idleWorkerCount = idleWorkerCount
        self.busyWorkerCount = busyWorkerCount
        self.pendingCount = pendingCount



@implementer(IWorker)
class Team(object):
    """
    
    """

    def __init__(self, createCoordinator, createWorker, logException):
        """
        
        """
        self._hasQuit = Quit()
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
        @self._coordinator.do
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
        self._coordinator.do(lambda: self._quitIdlers(n))


    def _quitIdlers(self, n=None):
        """
        
        """
        if n is None:
            n = len(self._idle)
        toQuit, self._idle = self._idle[:n], self._idle[n:]
        for idleWorker in toQuit:
            idleWorker.quit()


    def do(self, task):
        """
        
        """
        self._hasQuit.check()
        self._coordinator.do(lambda: self._coordinateThisTask(task))


    def _coordinateThisTask(self, task):
        """
        
        """
        worker = (self._idle.pop() if self._idle
                  else self._createWorker())
        if worker is None:
            # createWorker may return None if we're out of resources to
            # create workers.
            self._pending.append(task)
            return
        @worker.do
        def doWork():
            try:
                task()
            except:
                self._logException()

            @self._coordinator.do
            def idleAndPending():
                self._idle.add(worker)
                if self._pending:
                    # Re-try the first enqueued thing.
                    # (Explicitly do _not_ honor _hasQuit.)
                    self._coordinateThisTask(self._pending.popleft())
                elif self._hasQuit:
                    self._quitIdlers()


    def quit(self):
        """
        
        """
        self._hasQuit.set()
        # In case all the workers are idle when we do this.
        self._coordinator.do(self._quitIdlers)



