
from zope.interface import implementer

from ._ithreads import IWorker
from ._convenience import Quit


@implementer(IWorker)
class ReactorWorker(object):
    """
    
    """
    def __init__(self, reactor, quitStops=False):
        """
        
        """
        self._reactor = reactor
        self._hasQuit = Quit()
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
