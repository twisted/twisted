
from zope.interface import implementer
from ._ithreads import IExclusiveWorker
from ._convenience import Quit

@implementer(IExclusiveWorker)
class ReactorWorker(object):
    """
    A L{ReactorWorker} causes the work to be done in the reactor.

    This exclusive worker implementation ensures exclusivity by performing all
    work on the reactor thread.
    """

    def __init__(self, reactor, stopOnQuit=False):
        """
        Create a L{ReactorWorker} from a reactor.

        @param reactor: the reactor where we should perform the work passed to
            this worker.
        @type reactor: a provider of
            L{twisted.internet.interfaces.IReactorFromThreads} and
            L{twisted.internet.interfaces.IReactorCore}

        @param stopOnQuit: A flag indicating whether the C{quit} method of this
            worker should cause the reactor to stop.  If this L{ReactorWorker}
            should "own" the reactor and terminate your program when it's told
            to stop, then this should be C{True}; otherwise, and by default, it
            should be C{False}.
        @type stopOnQuit: L{bool}
        """
        self._reactor = reactor
        self._quit = Quit()
        self._stopOnQuit = stopOnQuit


    def do(self, work):
        """
        Invoke this work on the reactor.
        """
        self._quit.check()
        self._reactor.callFromThread(work)


    def quit(self):
        """
        Quit this worker, potentially stopping the reactor if C{stopOnQuit} was
        passed to this L{ReactorWorker}'s constructor.
        """
        self._quit.set()
        if self._stopOnQuit:
            self._reactor.callFromThread(self.reactor.stop)
