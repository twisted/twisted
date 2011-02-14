# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorTime}.
"""

__metaclass__ = type

from twisted.internet.test.reactormixins import ReactorBuilder


class TimeTestsBuilder(ReactorBuilder):
    """
    Builder for defining tests relating to L{IReactorTime}.
    """
    def test_delayedCallStopsReactor(self):
        """
        The reactor can be stopped by a delayed call.
        """
        reactor = self.buildReactor()
        reactor.callLater(0, reactor.stop)
        reactor.run()


globals().update(TimeTestsBuilder.makeTestCaseClasses())
