# -*- test-case-name: twisted.test.test_task -*-
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

"""Scheduling utility methods and classes.

API Stability: Unstable

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

from twisted.python.runtime import seconds

from twisted.internet import reactor
from twisted.internet import defer

class LoopingCall:
    """Call a function repeatedly.

    @ivar f: The function to call.
    @ivar a: A tuple of arguments to pass the function.
    @ivar kw: A dictionary of keyword arguments to pass to the function.
    """

    call = None
    running = False
    deferred = None
    interval = None
    count = None
    starttime = None

    def __init__(self, f, *a, **kw):
        self.f = f
        self.a = a
        self.kw = kw

    def start(self, interval):
        """Start running function every interval seconds.

        @param interval: The number of seconds between calls.  May be less than
        one.  Precision will depend on the underlying platform, the available
        hardware, and the load on the system.

        @return: A Deferred whose callback will be invoked with C{self} when
        C{self.stop} is called, or whose errback will be invoked if the function
        raises an exception.
        """
        assert not self.running
        self.running = True
        d = self.deferred = defer.Deferred()
        self.starttime = seconds()
        self.count = 0
        self.interval = interval
        self._loop()
        return d

    def stop(self):
        """Stop running function."""
        assert self.running
        self.running = False
        if self.call is not None:
            self.call.cancel()
            self.call = None
        d, self.deferred = self.deferred, None
        d.callback(self)

    def _loop(self):
        self.call = None
        try:
            self.f(*self.a, **self.kw)
        except:
            d, self.deferred = self.deferred, None
            d.errback()
            return

        fromNow = self.starttime - seconds()

        while self.running:
            self.count += 1
            fromStart = self.count * self.interval
            delay = fromNow + fromStart
            if delay > 0:
                self.call = reactor.callLater(delay, self._loop)
                return
