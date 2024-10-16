# -*- test-case-name: twisted._threads.test.test_memory -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of an in-memory worker that defers execution.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable, Literal

from zope.interface import implementer

from ._convenience import Quit
from ._ithreads import IExclusiveWorker


class NoMore(Enum):
    Work = auto()


NoMoreWork = NoMore.Work


@implementer(IExclusiveWorker)
class MemoryWorker:
    """
    An L{IWorker} that queues work for later performance.

    @ivar _quit: a flag indicating
    @type _quit: L{Quit}
    """

    def __init__(
        self,
        pending: Callable[[], list[Callable[[], object] | Literal[NoMore.Work]]] = list,
    ) -> None:
        """
        Create a L{MemoryWorker}.
        """
        self._quit = Quit()
        self._pending = pending()

    def do(self, work: Callable[[], object]) -> None:
        """
        Queue some work for to perform later; see L{createMemoryWorker}.

        @param work: The work to perform.
        """
        self._quit.check()
        self._pending.append(work)

    def quit(self) -> None:
        """
        Quit this worker.
        """
        self._quit.set()
        self._pending.append(NoMoreWork)


def createMemoryWorker() -> tuple[MemoryWorker, Callable[[], bool]]:
    """
    Create an L{IWorker} that does nothing but defer work, to be performed
    later.

    @return: a worker that will enqueue work to perform later, and a callable
        that will perform one element of that work.
    """

    def perform() -> bool:
        if not worker._pending:
            return False
        peek = worker._pending[0]
        if peek is NoMoreWork:
            return False
        worker._pending.pop(0)
        peek()
        return True

    worker = MemoryWorker()
    return (worker, perform)
