
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""A Queue subclass that supports timeouts."""

# System Imports
import Queue, time


_time = time.time
_sleep = time.sleep


class TimedOut(Exception):
    pass


class TimeoutQueue(Queue.Queue):
    """A thread-safe queue that supports timeouts"""
    
    def __init__(self, max=0):
        Queue.Queue.__init__(self, max)
    
    def wait(self, timeout):
        """Wait until the queue isn't empty. Raises TimedOut if still empty."""
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

