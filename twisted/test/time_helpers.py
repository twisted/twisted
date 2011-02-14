# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helper class to writing deterministic time-based unit tests.

Do not use this module.  It is a lie.  See L{twisted.internet.task.Clock}
instead.
"""

import warnings
warnings.warn(
    "twisted.test.time_helpers is deprecated since Twisted 10.0.  "
    "See twisted.internet.task.Clock instead.",
    category=DeprecationWarning, stacklevel=2)


class Clock(object):
    """
    A utility for monkey-patches various parts of Twisted to use a
    simulated timing mechanism. DO NOT use this class. Use
    L{twisted.internet.task.Clock}.
    """
    rightNow = 0.0

    def __call__(self):
        """
        Return the current simulated time.
        """
        return self.rightNow

    def install(self):
        """
        Monkeypatch L{twisted.internet.reactor.seconds} to use
        L{__call__} as a time source
        """
        # Violation is fun.
        from twisted.internet import reactor
        self.reactor_original = reactor.seconds
        reactor.seconds = self

    def uninstall(self):
        """
        Remove the monkeypatching of L{twisted.internet.reactor.seconds}.
        """
        from twisted.internet import reactor
        reactor.seconds = self.reactor_original

    def adjust(self, amount):
        """
        Adjust the current simulated time upward by the given C{amount}.

        Note that this does not cause any scheduled calls to be run.
        """
        self.rightNow += amount

    def pump(self, reactor, timings):
        """
        Iterate the given C{reactor} with increments of time specified
        by C{timings}.

        For each timing, the simulated time will be L{adjust}ed and
        the reactor will be iterated twice.
        """
        timings = list(timings)
        timings.reverse()
        self.adjust(timings.pop())
        while timings:
            self.adjust(timings.pop())
            reactor.iterate()
            reactor.iterate()

