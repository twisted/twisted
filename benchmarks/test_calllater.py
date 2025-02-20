"""Tests for scheduled events."""

import pytest

from twisted.internet.base import ReactorBase


class ReactorWithRiggedTime(ReactorBase):
    """
    Allows controlling the passed time while benchmarking C{ReactorBase}.
    """

    _currentTime = 0.0

    def seconds(self) -> float:
        """
        Override the regular time function in C{ReactorBase}.
        """
        return self._currentTime

    def advance(self, seconds: float) -> None:
        """
        Advance time by the given numbe of seconds.
        """
        self._currentTime += seconds

    def installWaker(self) -> None:
        """
        Subclasses of C{ReactorBase} are required to implement this.
        """
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
        reactor = ReactorWithRiggedTime()
        for time in timestamps:
            reactor.callLater(time, lambda: None)
        for _ in range(len(timestamps)):
            reactor.advance(reactor.timeout() or 0)
            reactor.runUntilCurrent()
        return reactor

    reactor = benchmark(go)
    assert not reactor._pendingTimedCalls
    assert not reactor._newTimedCalls
