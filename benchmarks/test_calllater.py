"""Tests for scheduled events."""

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


def test_spaced_out_events(benchmark):
    """
    Add spaced out events, then run them all.
    """

    def go():
        reactor = Reactor()
        for i in range(100):
            reactor.callLater(i, lambda: None)
        for _ in range(100):
            reactor.runUntilCurrent()
            reactor.advance(1)
        return reactor

    reactor = benchmark(go)
    assert not reactor._pendingTimedCalls
    assert not reactor._newTimedCalls
