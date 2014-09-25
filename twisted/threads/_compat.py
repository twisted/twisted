
from Queue import Queue

from . import Team, ThreadWorker

from twisted.python.log import err
from twisted.python.threadpool import ThreadPool
from twisted.python.failure import Failure

class TeamPool(ThreadPool, object):
    """
    
    """

    def __init__(self, minthreads=5, maxthreads=20, name=None,
                 createCoordinator=None):
        """
        
        """
        super(TeamPool, self).__init__(minthreads=minthreads,
                                         maxthreads=maxthreads,
                                         name=name)
        if createCoordinator is None:
            createCoordinator = ThreadWorker
        def workerCreator(result):
            # Called only from the workforce's coordinator.
            self.working += 1
            if self.working >= self.max:
                return None
            return ThreadWorker(
                lambda *a, **k: self.threadFactory(
                    *a, name=self._generateName(), **k
                ),
                Queue
            )
        self._team = Team(
            createCoordinator=createCoordinator,
            createWorker=workerCreator,
            logException=err
        )


    def callInThreadWithCallback(self, onResult, f, *a, **kw):
        """
        
        """
        def doIt():
            try:
                value = f(*a, **kw)
            except:
                onResult(Failure())
            else:
                onResult(value)
        self.callInThread(doIt)


    def callInThread(self, f, *a, **kw):
        """
        
        """
        self._workforce.do(lambda: f(*a, **kw))



