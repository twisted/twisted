# -*- test-case-name: twisted.threads.test.test_memory -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of an in-memory worker that defers execution.
"""

from zope.interface import implementer
from . import IWorker
from ._convenience import Quit

@implementer(IWorker)
class MemoryWorker(object):
    """
    An L{IWorker} that queues work for later performance.

    @ivar _quit: a flag indicating
    @type _quit: L{Quit}
    """

    def __init__(self):
        """
        Create a L{MemoryWorker}.
        """
        self._quit = Quit()
        self._pending = []


    def do(self, work):
        """
        Queue some work for L{MemoryWorker.perform} to perform later.

        @param work: The work to perform.
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
