
"""
Implementation of an in-memory worker that defers execution.
"""

from zope.interface import implementer
from . import IWorker
from ._convenience import Quit

@implementer(IWorker)
class MemoryWorker(object):
    """
    
    """
    def __init__(self):
        """
        
        """
        self._quit = Quit()
        self._pending = []


    def do(self, work):
        """
        
        """
        self._quit.check()
        self._pending.append(work)


    def quit(self):
        """
        Quit this worker.
        """
        self._quit.set()


    def perform(self):
        """
        Perform one unit of work.
        """
        self._quit.check()
        self._pending.pop(0)()
