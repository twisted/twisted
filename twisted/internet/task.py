# -*- test-case-name: twisted.test.test_task -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Scheduling utility methods and classes.

API Stability: Unstable

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

__metaclass__ = type

import time

from twisted.python.runtime import seconds
from twisted.python import reflect

from twisted.internet import defer


class LoopingCall:
    """Call a function repeatedly.

    @ivar f: The function to call.
    @ivar a: A tuple of arguments to pass the function.
    @ivar kw: A dictionary of keyword arguments to pass to the function.

    If C{f} returns a deferred, rescheduling will not take place until the
    deferred has fired. The result value is ignored.
    """

    call = None
    running = False
    deferred = None
    interval = None
    count = None
    starttime = None

    def _callLater(self, delay):
        from twisted.internet import reactor
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
        invoked when the function raises an exception or returned a
        deferred that has its errback invoked.
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
        def cb(result):
            if self.running:
                self._reschedule()
            else:
                d, self.deferred = self.deferred, None
                d.callback(self)

        def eb(failure):
            self.running = False
            d, self.deferred = self.deferred, None
            d.errback(failure)

        self.call = None
        d = defer.maybeDeferred(self.f, *self.a, **self.kw)
        d.addCallback(cb)
        d.addErrback(eb)

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



class SchedulerStopped(Exception):
    """
    The operation could not complete because the scheduler was stopped in
    progress or was already stopped.
    """



class _Timer(object):
    MAX_SLICE = 0.01
    def __init__(self):
        self.end = time.time() + self.MAX_SLICE


    def __call__(self):
        return time.time() >= self.end



_EPSILON = 0.00000001
def _defaultScheduler(x):
    from twisted.internet import reactor
    return reactor.callLater(_EPSILON, x)



class Cooperator(object):
    """
    Cooperative task scheduler.
    """

    def __init__(self,
                 terminationPredicateFactory=_Timer,
                 scheduler=_defaultScheduler,
                 started=True):
        """
        Create a scheduler-like object to which iterators may be added.

        @param terminationPredicateFactory: A no-argument callable which will
        be invoked at the beginning of each step and should return a
        no-argument callable which will return False when the step should be
        terminated.  The default factory is time-based and allows iterators to
        run for 1/100th of a second at a time.

        @param scheduler: A one-argument callable which takes a no-argument
        callable and should invoke it at some future point.  This will be used
        to schedule each step of this Cooperator.

        @param started: A boolean which indicates whether iterators should be
        stepped as soon as they are added, or if they will be queued up until
        L{Cooperator.start} is called.
        """
        self.iterators = []
        self._metarator = iter(())
        self._terminationPredicateFactory = terminationPredicateFactory
        self._scheduler = scheduler
        self._delayedCall = None
        self._stopped = False
        self._started = started


    def coiterate(self, iterator, doneDeferred=None):
        """
        Add an iterator to the list of iterators I am currently running.

        @return: a Deferred that will fire when the iterator finishes.
        """
        if doneDeferred is None:
            doneDeferred = defer.Deferred()
        if self._stopped:
            doneDeferred.errback(SchedulerStopped())
            return doneDeferred
        self.iterators.append((iterator, doneDeferred))
        self._reschedule()
        return doneDeferred


    def _tasks(self):
        terminator = self._terminationPredicateFactory()
        while self.iterators:
            for i in self._metarator:
                yield i
                if terminator():
                    return
            self._metarator = iter(self.iterators)


    def _tick(self):
        """
        Run one scheduler tick.
        """
        self._delayedCall = None
        for taskObj in self._tasks():
            iterator, doneDeferred = taskObj
            try:
                result = iterator.next()
            except StopIteration:
                self.iterators.remove(taskObj)
                doneDeferred.callback(iterator)
            except:
                self.iterators.remove(taskObj)
                doneDeferred.errback()
            else:
                if isinstance(result, defer.Deferred):
                    self.iterators.remove(taskObj)
                    def cbContinue(result, taskObj=taskObj):
                        self.coiterate(*taskObj)
                    result.addCallbacks(cbContinue, doneDeferred.errback)
        self._reschedule()


    _mustScheduleOnStart = False
    def _reschedule(self):
        if not self._started:
            self._mustScheduleOnStart = True
            return
        if self._delayedCall is None and self.iterators:
            self._delayedCall = self._scheduler(self._tick)


    def start(self):
        """
        Begin scheduling steps.
        """
        self._stopped = False
        self._started = True
        if self._mustScheduleOnStart:
            del self._mustScheduleOnStart
            self._reschedule()


    def stop(self):
        """
        Stop scheduling steps.  Errback the completion Deferreds of all
        iterators which have been added and forget about them.
        """
        self._stopped = True
        for iterator, doneDeferred in self.iterators:
            doneDeferred.errback(SchedulerStopped())
        self.iterators = []
        if self._delayedCall is not None:
            self._delayedCall.cancel()
            self._delayedCall = None



_theCooperator = Cooperator()
def coiterate(iterator):
    """
    Cooperatively iterate over the given iterator, dividing runtime between it
    and all other iterators which have been passed to this function and not yet
    exhausted.
    """
    return _theCooperator.coiterate(iterator)



__all__ = [
    'LoopingCall',

    'SchedulerStopped', 'Cooperator', 'coiterate',
    ]
