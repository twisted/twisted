# -*- test-case-name: twisted.test.test_task -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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

    def start(self, interval, now=True):
        """Start running function every interval seconds.

        @param interval: The number of seconds between calls.  May be less than
        one.  Precision will depend on the underlying platform, the available
        hardware, and the load on the system.
        
        @param now: If True, run this call right now.  Otherwise, wait until the
        interval has elapsed before beginning.

        @return: A Deferred whose callback will be invoked with C{self} when
        C{self.stop} is called, or whose errback will be invoked if the function
        raises an exception.
        """
        assert not self.running
        if interval < 0:
            raise ValueError, "interval must be >= 0"
        self.running = True
        d = self.deferred = defer.Deferred()
        self.starttime = seconds()
        self.count = 0
        self.interval = interval
        if now:
            self._loop()
        else:
            self._reschedule()
        return d

    def stop(self):
        """Stop running function."""
        assert self.running
        reactor.callLater(0, self._reallyStop)
    
    def _reallyStop(self):
        if not self.running:
            return
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
            self.running = False
            d, self.deferred = self.deferred, None
            d.errback()
        else:
            self._reschedule()
    
    def _reschedule(self):
        if self.interval == 0:
            self.call = reactor.callLater(0, self._loop)
            return

        fromNow = self.starttime - seconds()

        while self.running:
            self.count += 1
            fromStart = self.count * self.interval
            delay = fromNow + fromStart
            if delay > 0:
                self.call = reactor.callLater(delay, self._loop)
                return
