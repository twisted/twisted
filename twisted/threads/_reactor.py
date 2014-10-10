# -*- test-case-name: twisted.threads.test.test_reactor -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Integration of twisted.threads with twisted.internet.
"""

from zope.interface import implementer

from ._ithreads import IWorker
from ._convenience import Quit


@implementer(IWorker)
class ReactorWorker(object):
    """
    An L{IWorker} implementation that wraps a reactor, via C{callFromThread}.
    """
    def __init__(self, reactor, quitStops=False):
        """
        @param reactor: an object with a C{callFromThread} method, and possibly
            a C{stop} method.

        @param quitStops: Does C{quit} call C{stop} on the underlying reactor?
        """
        self._reactor = reactor
        self._hasQuit = Quit()
        self._quitStops = quitStops


    def do(self, work):
        """
        Do this work in the reactor thread.

        @param work: The work to perform in the reactor.
        @type work: 0-argument callable
        """
        self._hasQuit.check()
        self._reactor.callFromThread(work)


    def quit(self):
        """
        Quit this worker, possibly stopping the reactor if C{quitStops=True}
        was passed to the constructor.
        """
        self._hasQuit.set()
        if self._quitStops:
            self._reactor.stop()
