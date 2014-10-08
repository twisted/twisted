# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.threads._team}.
"""

from twisted.trial.unittest import SynchronousTestCase

from twisted.python.context import call, get
from twisted.python.components import proxyForInterface

from twisted.python.logger import Logger

from .. import IWorker, Team, createMemoryWorker, AlreadyQuit

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

        @param work: the work to pass on to the real worker.
        """
        super(ContextualWorker, self).do(lambda: call(self._context, work))



class TeamTests(SynchronousTestCase):
    """
    Tests for L{twisted.threads.Team}
    """

    log = Logger()

    def setUp(self):
        """
        Set up a L{Team} with inspectable, synchronous workers that can be
        single-stepped.
        """
        coordinator, self.coordinate = createMemoryWorker()
        self.coordinator = ContextualWorker(coordinator, worker="coordinator")
        self.workerPerformers = []
        self.allWorkersEver = []
        def createWorker():
            worker, performer = createMemoryWorker()
            self.workerPerformers.append(performer)
            cw = ContextualWorker(worker, worker=len(self.workerPerformers))
            self.allWorkersEver.append(cw)
            return cw
        self.team = Team(lambda: coordinator, createWorker, None)


    def performAllOutstandingWork(self):
        """
        Perform all work on the coordinator and worker performers that needs to
        be done.
        """
        self.coordinate()
        for performer in self.workerPerformers[:]:
            try:
                performer()
            except AlreadyQuit:
                self.workerPerformers.remove(performer)


    def test_doDoesWorkInWorker(self):
        """
        L{Team.do} does the work in a worker created by the createWorker
        callable.
        """
        def something():
            something.who = get("worker")
        self.team.do(something)
        self.performAllOutstandingWork()
        self.assertEqual(something.who, 1)


    def test_growCreatesIdleWorkers(self):
        """
        L{Team.grow} increases the number of available idle workers.
        """
        self.team.grow(5)
        self.performAllOutstandingWork()
        self.assertEqual(len(self.workerPerformers), 5)


    def test_shrinkQuitsWorkers(self):
        """
        L{Team.shrink} will quit workers.
        """
        self.team.grow(5)
        self.performAllOutstandingWork()
        self.team.shrink(3)
        self.performAllOutstandingWork()
        self.assertEqual(len(self.team._idle), 2)
