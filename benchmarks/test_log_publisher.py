"""
Benchmarks for LogPublisher event dispatching.
"""

from typing import List

from twisted.logger import LogEvent, LogLevel, LogPublisher


class DummyObserver:
    """
    An observer that just records the last event it received.
    """

    def __init__(self):
        self.last_event = None

    def __call__(self, event: LogEvent):
        self.last_event = event


def test_log_publisher_call_dispatch(benchmark):
    """
    Dispatch a single event to a single publisher that has multiple observers.
    """
    num_observers = 2000

    observers: List[DummyObserver] = [DummyObserver() for _ in range(num_observers)]
    publisher = LogPublisher(*observers)

    event = {
        "log_level": LogLevel.info,
        "log_namespace": "benchmark",
        "log_format": "This is a benchmark event.",
    }

    def go():
        publisher(event)

    benchmark(go)


def test_log_publisher_add_remove(benchmark):
    """
    Benchmark the cost of adding and removing observers repeatedly.
    """
    num_observers = 2000

    publisher = LogPublisher()
    observers = [DummyObserver() for _ in range(num_observers)]

    def go():
        for obs in observers:
            publisher.addObserver(obs)
        for obs in observers:
            publisher.removeObserver(obs)

    benchmark(go)
