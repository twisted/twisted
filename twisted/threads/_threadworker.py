
from zope.interface import implementer
from .ithreads import IWorker
from ._convenience import Quit


_stop = object()

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
        self._hasQuit = Quit()


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



