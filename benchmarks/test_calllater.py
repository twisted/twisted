"""Tests for scheduled events."""

from twisted.internet.base import ReactorBase


class Reactor(ReactorBase):
    """
    Implement minimal methods a subclass needs.
    """

    def installWaker(self):
        pass


def test_spaced_out_events(benchmark):
    """
    Add spaced out events, then run them all.
    """

    def go():
        reactor = Reactor()
        return reactor

    reactor = benchmark(go)
    assert not reactor._pendingTimedCalls
    assert not reactor._newTimedCalls
