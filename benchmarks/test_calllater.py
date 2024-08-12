"""Tests for scheduled events."""

import pytest

from twisted.internet.base import ReactorBase


class Reactor(ReactorBase):
    """
    Implement minimal methods a subclass needs.
    """
    _currentTime = 0.0

    def seconds(self) -> float:
        return self._currentTime

    def advance(self, seconds: float):
        self._currentTime += seconds

    def installWaker(self):
        pass


@pytest.mark.parametrize("reversed_times", [False, True])
def test_spaced_out_events(benchmark, reversed_times):
    """
    Add spaced out events, then run them all.
    """
    timestamps = list(range(100))
    if reversed_times:
        timestamps.reverse()

    def go():
        reactor = Reactor()
        for time in timestamps:
            reactor.callLater(time, lambda: None)
        for _ in range(len(timestamps)):
            reactor.advance(reactor.timeout() or 0)
            reactor.runUntilCurrent()
        return reactor

    reactor = benchmark(go)
    assert not reactor._pendingTimedCalls
    assert not reactor._newTimedCalls
