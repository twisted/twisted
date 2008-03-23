# -*- test-case-name: twisted.test.test_timeoutqueue -*-
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A Queue subclass that supports timeouts.
"""

# System Imports
import Queue, time, warnings


_time = time.time
_sleep = time.sleep


class TimedOut(Exception):
    pass


class TimeoutQueue(Queue.Queue):
    """
    A thread-safe queue that supports timeouts.
    """

    def __init__(self, max=0):
        warnings.warn("timeoutqueue is deprecated since Twisted 8.0",
                      category=DeprecationWarning, stacklevel=2)
        Queue.Queue.__init__(self, max)

    def wait(self, timeout):
        """
        Wait until the queue isn't empty. Raises TimedOut if still empty.
        """
        endtime = _time() + timeout
        delay = 0.0005 # 500 us -> initial delay of 1 ms
        while 1:
            gotit = not self.empty()
            if gotit:
                break
            remaining = endtime - _time()
            if remaining <= 0:
                raise TimedOut, "timed out."
            delay = min(delay * 2, remaining, .05)
            _sleep(delay)


__all__ = ["TimeoutQueue", "TimedOut"]

