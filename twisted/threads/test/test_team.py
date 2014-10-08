# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.threads._team}.
"""

from twisted.trial.unittest import SynchronousTestCase

from twisted.python.context import call, get
from twisted.python.components import proxyForInterface

from twisted.python.logger import Logger

from .. import IWorker, Team, createMemoryWorker

class ContextualWorker(proxyForInterface(IWorker, "_realWorker")):
    """
    A worker implementation that supplies a context.
    """

    def __init__(self, realWorker, **ctx):
        """
        Create with a real worker and a context.
        """
        self._realWorker = realWorker
        self._context = ctx


    def do(self, work):
        """
        Perform the given work with the context given to __init__.
        """
        return (super(ContextualWorker, self)
                .do(lambda: call(self._context, work)))



class TeamTests(SynchronousTestCase):
    """
    Tests for L{twisted.threads.Team}
    """

    log = Logger()

    def test_doDoesWorkInWorker(self):
        """
        L{Team.do} does the work in a worker created by the createWorker
        callable.
        """
        coordinator, coordinate = createMemoryWorker()
        coordinator = ContextualWorker(coordinator, worker="coordinator")
        workerPerformers = []
        def createWorker():
            worker, performer = createMemoryWorker()
            workerPerformers.append(performer)
            return ContextualWorker(worker, worker=len(workerPerformers))
        team = Team(lambda: coordinator, createWorker, None)
        def something():
            something.who = get("worker")
        team.do(something)
        coordinate()
        for performer in workerPerformers:
            performer()
        self.assertEqual(something.who, 1)
