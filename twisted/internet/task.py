# -*- test-case-name: twisted.test.test_task -*-
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Scheduling utility methods and classes.

@author: Jp Calderone
"""

__metaclass__ = type

import time

from zope.interface import implements

from twisted.python import reflect

from twisted.internet import base, defer
from twisted.internet.interfaces import IReactorTime


class LoopingCall:
    """Call a function repeatedly.

    If C{f} returns a deferred, rescheduling will not take place until the
    deferred has fired. The result value is ignored.

    @ivar f: The function to call.
    @ivar a: A tuple of arguments to pass the function.
    @ivar kw: A dictionary of keyword arguments to pass to the function.
    @ivar clock: A provider of
        L{twisted.internet.interfaces.IReactorTime}.  The default is
        L{twisted.internet.reactor}. Feel free to set this to
        something else, but it probably ought to be set *before*
        calling L{start}.

    @type _lastTime: C{float}
    @ivar _lastTime: The time at which this instance most recently scheduled
        itself to run.
    """

    call = None
    running = False
    deferred = None
    interval = None
    _lastTime = 0.0
    starttime = None

    def __init__(self, f, *a, **kw):
        self.f = f
        self.a = a
        self.kw = kw
        from twisted.internet import reactor
        self.clock = reactor


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
        self.starttime = self.clock.seconds()
        self._lastTime = self.starttime
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
        """
        Schedule the next iteration of this looping call.
        """
        if self.interval == 0:
            self.call = self.clock.callLater(0, self)
            return

        currentTime = self.clock.seconds()
        # Find how long is left until the interval comes around again.
        untilNextTime = (self._lastTime - currentTime) % self.interval
        # Make sure it is in the future, in case more than one interval worth
        # of time passed since the previous call was made.
        nextTime = max(
            self._lastTime + self.interval, currentTime + untilNextTime)
        # If the interval falls on the current time exactly, skip it and
        # schedule the call for the next interval.
        if nextTime == currentTime:
            nextTime += self.interval
        self._lastTime = nextTime
        self.call = self.clock.callLater(nextTime - currentTime, self)


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



class Clock:
    """
    Provide a deterministic, easily-controlled implementation of
    L{IReactorTime.callLater}.  This is commonly useful for writing
    deterministic unit tests for code which schedules events using this API.
    """
    implements(IReactorTime)

    rightNow = 0.0

    def __init__(self):
        self.calls = []

    def seconds(self):
        """
        Pretend to be time.time().  This is used internally when an operation
        such as L{IDelayedCall.reset} needs to determine a a time value
        relative to the current time.

        @rtype: C{float}
        @return: The time which should be considered the current time.
        """
        return self.rightNow


    def callLater(self, when, what, *a, **kw):
        """
        See L{twisted.internet.interfaces.IReactorTime.callLater}.
        """
        dc =  base.DelayedCall(self.seconds() + when,
                               what, a, kw,
                               self.calls.remove,
                               lambda c: None,
                               self.seconds)
        self.calls.append(dc)
        self.calls.sort(lambda a, b: cmp(a.getTime(), b.getTime()))
        return dc

    def getDelayedCalls(self):
        """
        See L{twisted.internet.interfaces.IReactorTime.getDelayedCalls}
        """
        return self.calls

    def advance(self, amount):
        """
        Move time on this clock forward by the given amount and run whatever
        pending calls should be run.

        @type amount: C{float}
        @param amount: The number of seconds which to advance this clock's
        time.
        """
        self.rightNow += amount
        while self.calls and self.calls[0].getTime() <= self.seconds():
            call = self.calls.pop(0)
            call.called = 1
            call.func(*call.args, **call.kw)


    def pump(self, timings):
        """
        Advance incrementally by the given set of times.

        @type timings: iterable of C{float}
        """
        for amount in timings:
            self.advance(amount)


def deferLater(clock, delay, callable, *args, **kw):
    """
    Call the given function after a certain period of time has passed.

    @type clock: L{IReactorTime} provider
    @param clock: The object which will be used to schedule the delayed
        call.

    @type delay: C{float} or C{int}
    @param delay: The number of seconds to wait before calling the function.

    @param callable: The object to call after the delay.

    @param *args: The positional arguments to pass to C{callable}.

    @param **kw: The keyword arguments to pass to C{callable}.

    @rtype: L{defer.Deferred}

    @return: A deferred that fires with the result of the callable when the
        specified time has elapsed.
    """
    d = defer.Deferred()
    d.addCallback(lambda ignored: callable(*args, **kw))
    clock.callLater(delay, d.callback, None)
    return d



__all__ = [
    'LoopingCall',

    'Clock',

    'SchedulerStopped', 'Cooperator', 'coiterate',

    'deferLater',
    ]
