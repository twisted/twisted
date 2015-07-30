# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

try:
    from Queue import Queue
except ImportError:
    from queue import Queue

from threading import Thread, Lock, local as LocalStorage

from ._threadworker import ThreadWorker, LockWorker
from ._team import Team

# TODO: replace with logger
from twisted.python.log import err

def teamWithLimit(currentLimit,
                  threadFactory=lambda target: Thread(target=target)):
    """
    Create a thread pool using a queue and locks internally.
    """
    def limitedWorkerCreator():
        stats = team.statistics()
        if stats.busyWorkerCount + stats.idleWorkerCount >= currentLimit():
            return None
        return ThreadWorker(threadFactory, Queue)

    team = Team(lambda: LockWorker(Lock(), LocalStorage()),
                createWorker=limitedWorkerCreator,
                logException=err)
    return team
