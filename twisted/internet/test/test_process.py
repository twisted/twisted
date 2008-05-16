# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorProcess}.
"""

__metaclass__ = type

import warnings, sys, signal

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.error import PotentialZombieWarning

class ProcessTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorProcess}.
    """
    def spawnProcess(self, reactor):
        """
        Call C{reactor.spawnProcess} with some simple arguments.  Do this here
        so that code object referenced by the stack frame has a C{co_filename}
        attribute set to this file so that L{TestCase.assertWarns} can be used.
        """
        reactor.spawnProcess(
            ProcessProtocol(), sys.executable, [sys.executable, "-c", ""])


    def test_spawnProcessTooEarlyWarns(self):
        """
        C{reactor.spawnProcess} emits a warning if it is called before
        C{reactor.run}.

        If you can figure out a way to make it safe to run
        C{reactor.spawnProcess} before C{reactor.run}, you may delete the
        warning and this test.
        """
        reactor = self.buildReactor()
        self.assertWarns(
            PotentialZombieWarning,
            PotentialZombieWarning.MESSAGE, __file__,
            self.spawnProcess, reactor)


    def test_callWhenRunningSpawnProcessWarningFree(self):
        """
        L{PotentialZombieWarning} is not emitted when the reactor is run after
        C{reactor.callWhenRunning(reactor.spawnProcess, ...)} has been called.
        """
        events = []
        self.patch(warnings, 'warn', lambda *a, **kw: events.append(a))
        reactor = self.buildReactor()
        reactor.callWhenRunning(self.spawnProcess, reactor)
        reactor.callWhenRunning(reactor.stop)
        reactor.run()
        self.assertFalse(events)


    if getattr(signal, 'SIGCHLD', None) is None:
        skipMsg = "No SIGCHLD, no zombies possible."
        test_spawnProcessTooEarlyWarns.skip = skipMsg
        test_callWhenRunningSpawnProcessWarningFree.skip = skipMsg



globals().update(ProcessTestsBuilder.makeTestCaseClasses())
