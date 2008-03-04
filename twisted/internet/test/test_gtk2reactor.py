# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.gtk2reactor}.
"""

from twisted.trial.unittest import TestCase


class Gtk2ReactorTests(TestCase):
    """
    Tests for L{twisted.internet.gtk2reactor.Gtk2Reactor}.
    """
    def test_stopWhenRunning(self):
        """
        When C{reactor.stop} is scheduled with C{callWhenRunning},
        C{reactor.run} will return immediately, and without processing any
        timed events.
        """
        # This test *should* be part of a general reactor test suite that runs
        # tests cases against all reactor implementations.
        missed = []
        def calledTooLate():
            missed.append(True)
            reactor.crash()
        reactor = Gtk2Reactor(useGtk=False)
        reactor.callWhenRunning(reactor.stop)
        reactor.callLater(0, calledTooLate)
        reactor.run(installSignalHandlers=False)
        # XXX This explicit calls to clean up the waker should become obsolete
        # when bug #3063 is fixed. -radix, 2008-02-29. Fortunately it should
        # probably cause an error when bug #3063 is fixed, so it should be
        # removed in the same branch that fixes it.
        reactor.removeReader(reactor.waker)
        reactor.waker.connectionLost(None)
        if missed == [True]:
            self.fail("callWhenRunning reactor.stop did not take effect")

try:
    from twisted.internet.gtk2reactor import Gtk2Reactor
except ImportError:
    Gtk2ReactorTests.skip = "gtk2reactor is unavailable"
