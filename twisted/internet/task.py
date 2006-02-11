# -*- test-case-name: twisted.test.test_task -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Scheduling utility methods and classes.

API Stability: Unstable

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

__metaclass__ = type

from twisted.python.runtime import seconds
from twisted.python import reflect

from twisted.internet import reactor, defer

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

    def _callLater(self, delay):
        return reactor.callLater(delay, self)

    _seconds = staticmethod(seconds)

    def __init__(self, f, *a, **kw):
        self.f = f
        self.a = a
        self.kw = kw

    def start(self, interval, now=True):
        """Start running function every interval seconds.

        @param interval: The number of seconds between calls.  May be
        less than one.  Precision will depend on the underlying
        platform, the available hardware, and the load on the system.

        @param now: If True, run this call right now.  Otherwise, wait
        until the interval has elapsed before beginning.

        @return: A Deferred whose callback will be invoked with
        C{self} when C{self.stop} is called, or whose errback will be
        invoked if the function raises an exception.
        """
        assert not self.running, ("Tried to start an already running "
                                  "LoopingCall.")
        if interval < 0:
            raise ValueError, "interval must be >= 0"
        self.running = True
        d = self.deferred = defer.Deferred()
        self.starttime = self._seconds()
        self.count = 0
        self.interval = interval
        if now:
            self()
        else:
            self._reschedule()
        return d

    def stop(self):
        """Stop running function.
        """
        assert self.running, ("Tried to stop a LoopingCall that was "
                              "not running.")
        self.running = False
        if self.call is not None:
            self.call.cancel()
            self.call = None
            d, self.deferred = self.deferred, None
            d.callback(self)

    def __call__(self):
        self.call = None
        try:
            self.f(*self.a, **self.kw)
        except:
            self.running = False
            d, self.deferred = self.deferred, None
            d.errback()
        else:
            if self.running:
                self._reschedule()
            else:
                d, self.deferred = self.deferred, None
                d.callback(self)

    def _reschedule(self):
        if self.interval == 0:
            self.call = self._callLater(0)
            return

        fromNow = self.starttime - self._seconds()

        while self.running:
            self.count += 1
            fromStart = self.count * self.interval
            delay = fromNow + fromStart
            if delay > 0:
                self.call = self._callLater(delay)
                return

    def __repr__(self):
        if hasattr(self.f, 'func_name'):
            func = self.f.func_name
            if hasattr(self.f, 'im_class'):
                func = self.f.im_class.__name__ + '.' + func
        else:
            func = reflect.safe_repr(self.f)

        return 'LoopingCall<%r>(%s, *%s, **%s)' % (
            self.interval, func, reflect.safe_repr(self.a),
            reflect.safe_repr(self.kw))

__all__ = [
    'LoopingCall',
    ]
