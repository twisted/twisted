# -*- test-case-name: twisted.logger.test.test_capture -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Context manager for capturing logs.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import cast

from twisted.logger import globalLogPublisher
from ._interfaces import ILogObserver, LogEvent


@contextmanager
def capturedLogs() -> Iterator[Sequence[LogEvent]]:
    events: list[LogEvent] = []
    observer = cast(ILogObserver, events.append)

    globalLogPublisher.addObserver(observer)

    yield events

    globalLogPublisher.removeObserver(observer)
