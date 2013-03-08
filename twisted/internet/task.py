# -*- test-case-name: twisted.test.test_task,twisted.test.test_cooperator -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Scheduling utility methods and classes.
"""

from __future__ import division, absolute_import

__metaclass__ = type

import sys
import time

from zope.interface import implementer

from twisted.python import log
from twisted.python import _reflectpy3 as reflect
from twisted.python.failure import Failure

from twisted.internet import base, defer
from twisted.internet.interfaces import IReactorTime
from twisted.internet.error import ReactorNotRunning


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

    @type running: C{bool}
    @ivar running: A flag which is C{True} while C{f} is scheduled to be called
        (or is currently being called). It is set to C{True} when L{start} is
        called and set to C{False} when L{stop} is called or if C{f} raises an
        exception. In either case, it will be C{False} by the time the
        C{Deferred} returned by L{start} fires its callback or errback.

    @type _expectNextCallAt: C{float}
    @ivar _expectNextCallAt: The time at which this instance most recently
        scheduled itself to run.

    @type _realLastTime: C{float}
    @ivar _realLastTime: When counting skips, the time at which the skip
        counter was last invoked.

    @type _runAtStart: C{bool}
    @ivar _runAtStart: A flag indicating whether the 'now' argument was passed
        to L{LoopingCall.start}.
    """

    call = None
    running = False
    deferred = None
    interval = None
    _expectNextCallAt = 0.0
    _runAtStart = False
    starttime = None

    def __init__(self, f, *a, **kw):
        self.f = f
        self.a = a
        self.kw = kw
        from twisted.internet import reactor
        self.clock = reactor


    def withCount(cls, countCallable):
        """
        An alternate constructor for L{LoopingCall} that makes available the
        number of calls which should have occurred since it was last invoked.

        Note that this number is an C{int} value; It represents the discrete
        number of calls that should have been made.  For example, if you are
        using a looping call to display an animation with discrete frames, this
        number would be the number of frames to advance.

        The count is normally 1, but can be higher. For example, if the reactor
        is blocked and takes too long to invoke the L{LoopingCall}, a Deferred
        returned from a previous call is not fired before an interval has
        elapsed, or if the callable itself blocks for longer than an interval,
        preventing I{itself} from being called.

        @param countCallable: A callable that will be invoked each time the
            resulting LoopingCall is run, with an integer specifying the number
            of calls that should have been invoked.

        @type countCallable: 1-argument callable which takes an C{int}

        @return: An instance of L{LoopingCall} with call counting enabled,
            which provides the count as the first positional argument.

        @rtype: L{LoopingCall}

        @since: 9.0
        """

        def counter():
            now = self.clock.seconds()
            lastTime = self._realLastTime
            if lastTime is None:
                lastTime = self.starttime
                if self._runAtStart:
                    lastTime -= self.interval
            self._realLastTime = now
            lastInterval = self._intervalOf(lastTime)
            thisInterval = self._intervalOf(now)
            count = thisInterval - lastInterval
            return countCallable(count)

        self = cls(counter)

        self._realLastTime = None

        return self

    withCount = classmethod(withCount)


    def _intervalOf(self, t):
        """
        Determine the number of intervals passed as of the given point in
        time.

        @param t: The specified time (from the start of the L{LoopingCall}) to
            be measured in intervals

        @return: The C{int} number of intervals which have passed as of the
            given point in time.
        """
        elapsedTime = t - self.starttime
        intervalNum = int(elapsedTime / self.interval)
        return intervalNum


    def start(self, interval, now=True):
        """
        Start running function every interval seconds.

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
            raise ValueError("interval must be >= 0")
        self.running = True
        d = self.deferred = defer.Deferred()
        self.starttime = self.clock.seconds()
        self._expectNextCallAt = self.starttime
        self.interval = interval
        self._runAtStart = now
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

    def reset(self):
        """
        Skip the next iteration and reset the timer.

        @since: 11.1
        """
        assert self.running, ("Tried to reset a LoopingCall that was "
                              "not running.")
        if self.call is not None:
            self.call.cancel()
            self.call = None
            self._expectNextCallAt = self.clock.seconds()
            self._reschedule()

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
        untilNextTime = (self._expectNextCallAt - currentTime) % self.interval
        # Make sure it is in the future, in case more than one interval worth
        # of time passed since the previous call was made.
        nextTime = max(
            self._expectNextCallAt + self.interval, currentTime + untilNextTime)
        # If the interval falls on the current time exactly, skip it and
        # schedule the call for the next interval.
        if nextTime == currentTime:
            nextTime += self.interval
        self._expectNextCallAt = nextTime
        self.call = self.clock.callLater(nextTime - currentTime, self)


    def __repr__(self):
        if hasattr(self.f, '__qualname__'):
            func = self.f.__qualname__
        elif hasattr(self.f, '__name__'):
            func = self.f.__name__
            if hasattr(self.f, 'im_class'):
                func = self.f.im_class.__name__ + '.' + func
        else:
            func = reflect.safe_repr(self.f)

        return 'LoopingCall<%r>(%s, *%s, **%s)' % (
            self.interval, func, reflect.safe_repr(self.a),
            reflect.safe_repr(self.kw))



class SchedulerError(Exception):
    """
    The operation could not be completed because the scheduler or one of its
    tasks was in an invalid state.  This exception should not be raised
    directly, but is a superclass of various scheduler-state-related
    exceptions.
    """



class SchedulerStopped(SchedulerError):
    """
    The operation could not complete because the scheduler was stopped in
    progress or was already stopped.
    """



class TaskFinished(SchedulerError):
    """
    The operation could not complete because the task was already completed,
    stopped, encountered an error or otherwise permanently stopped running.
    """



class TaskDone(TaskFinished):
    """
    The operation could not complete because the task was already completed.
    """



class TaskStopped(TaskFinished):
    """
    The operation could not complete because the task was stopped.
    """



class TaskFailed(TaskFinished):
    """
    The operation could not complete because the task died with an unhandled
    error.
    """



class NotPaused(SchedulerError):
    """
    This exception is raised when a task is resumed which was not previously
    paused.
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


class CooperativeTask(object):
    """
    A L{CooperativeTask} is a task object inside a L{Cooperator}, which can be
    paused, resumed, and stopped.  It can also have its completion (or
    termination) monitored.

    @see: L{Cooperator.cooperate}

    @ivar _iterator: the iterator to iterate when this L{CooperativeTask} is
        asked to do work.

    @ivar _cooperator: the L{Cooperator} that this L{CooperativeTask}
        participates in, which is used to re-insert it upon resume.

    @ivar _deferreds: the list of L{defer.Deferred}s to fire when this task
        completes, fails, or finishes.

    @type _deferreds: C{list}

    @type _cooperator: L{Cooperator}

    @ivar _pauseCount: the number of times that this L{CooperativeTask} has
        been paused; if 0, it is running.

    @type _pauseCount: C{int}

    @ivar _completionState: The completion-state of this L{CooperativeTask}.
        C{None} if the task is not yet completed, an instance of L{TaskStopped}
        if C{stop} was called to stop this task early, of L{TaskFailed} if the
        application code in the iterator raised an exception which caused it to
        terminate, and of L{TaskDone} if it terminated normally via raising
        C{StopIteration}.

    @type _completionState: L{TaskFinished}
    """

    def __init__(self, iterator, cooperator):
        """
        A private constructor: to create a new L{CooperativeTask}, see
        L{Cooperator.cooperate}.
        """
        self._iterator = iterator
        self._cooperator = cooperator
        self._deferreds = []
        self._pauseCount = 0
        self._completionState = None
        self._completionResult = None
        cooperator._addTask(self)


    def whenDone(self):
        """
        Get a L{defer.Deferred} notification of when this task is complete.

        @return: a L{defer.Deferred} that fires with the C{iterator} that this
            L{CooperativeTask} was created with when the iterator has been
            exhausted (i.e. its C{next} method has raised C{StopIteration}), or
            fails with the exception raised by C{next} if it raises some other
            exception.

        @rtype: L{defer.Deferred}
        """
        d = defer.Deferred()
        if self._completionState is None:
            self._deferreds.append(d)
        else:
            d.callback(self._completionResult)
        return d


    def pause(self):
        """
        Pause this L{CooperativeTask}.  Stop doing work until
        L{CooperativeTask.resume} is called.  If C{pause} is called more than
        once, C{resume} must be called an equal number of times to resume this
        task.

        @raise TaskFinished: if this task has already finished or completed.
        """
        self._checkFinish()
        self._pauseCount += 1
        if self._pauseCount == 1:
            self._cooperator._removeTask(self)


    def resume(self):
        """
        Resume processing of a paused L{CooperativeTask}.

        @raise NotPaused: if this L{CooperativeTask} is not paused.
        """
        if self._pauseCount == 0:
            raise NotPaused()
        self._pauseCount -= 1
        if self._pauseCount == 0 and self._completionState is None:
            self._cooperator._addTask(self)


    def _completeWith(self, completionState, deferredResult):
        """
        @param completionState: a L{TaskFinished} exception or a subclass
            thereof, indicating what exception should be raised when subsequent
            operations are performed.

        @param deferredResult: the result to fire all the deferreds with.
        """
        self._completionState = completionState
        self._completionResult = deferredResult
        if not self._pauseCount:
            self._cooperator._removeTask(self)

        # The Deferreds need to be invoked after all this is completed, because
        # a Deferred may want to manipulate other tasks in a Cooperator.  For
        # example, if you call "stop()" on a cooperator in a callback on a
        # Deferred returned from whenDone(), this CooperativeTask must be gone
        # from the Cooperator by that point so that _completeWith is not
        # invoked reentrantly; that would cause these Deferreds to blow up with
        # an AlreadyCalledError, or the _removeTask to fail with a ValueError.
        for d in self._deferreds:
            d.callback(deferredResult)


    def stop(self):
        """
        Stop further processing of this task.

        @raise TaskFinished: if this L{CooperativeTask} has previously
            completed, via C{stop}, completion, or failure.
        """
        self._checkFinish()
        self._completeWith(TaskStopped(), Failure(TaskStopped()))


    def _checkFinish(self):
        """
        If this task has been stopped, raise the appropriate subclass of
        L{TaskFinished}.
        """
        if self._completionState is not None:
            raise self._completionState


    def _oneWorkUnit(self):
        """
        Perform one unit of work for this task, retrieving one item from its
        iterator, stopping if there are no further items in the iterator, and
        pausing if the result was a L{defer.Deferred}.
        """
        try:
            result = next(self._iterator)
        except StopIteration:
            self._completeWith(TaskDone(), self._iterator)
        except:
            self._completeWith(TaskFailed(), Failure())
        else:
            if isinstance(result, defer.Deferred):
                self.pause()
                def failLater(f):
                    self._completeWith(TaskFailed(), f)
                result.addCallbacks(lambda result: self.resume(),
                                    failLater)



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
        no-argument callable which will return True when the step should be
        terminated.  The default factory is time-based and allows iterators to
        run for 1/100th of a second at a time.

        @param scheduler: A one-argument callable which takes a no-argument
        callable and should invoke it at some future point.  This will be used
        to schedule each step of this Cooperator.

        @param started: A boolean which indicates whether iterators should be
        stepped as soon as they are added, or if they will be queued up until
        L{Cooperator.start} is called.
        """
        self._tasks = []
        self._metarator = iter(())
        self._terminationPredicateFactory = terminationPredicateFactory
        self._scheduler = scheduler
        self._delayedCall = None
        self._stopped = False
        self._started = started


    def coiterate(self, iterator, doneDeferred=None):
        """
        Add an iterator to the list of iterators this L{Cooperator} is
        currently running.

        @param doneDeferred: If specified, this will be the Deferred used as
            the completion deferred.  It is suggested that you use the default,
            which creates a new Deferred for you.

        @return: a Deferred that will fire when the iterator finishes.
        """
        if doneDeferred is None:
            doneDeferred = defer.Deferred()
        CooperativeTask(iterator, self).whenDone().chainDeferred(doneDeferred)
        return doneDeferred


    def cooperate(self, iterator):
        """
        Start running the given iterator as a long-running cooperative task, by
        calling next() on it as a periodic timed event.

        @param iterator: the iterator to invoke.

        @return: a L{CooperativeTask} object representing this task.
        """
        return CooperativeTask(iterator, self)


    def _addTask(self, task):
        """
        Add a L{CooperativeTask} object to this L{Cooperator}.
        """
        if self._stopped:
            self._tasks.append(task) # XXX silly, I know, but _completeWith
                                     # does the inverse
            task._completeWith(SchedulerStopped(), Failure(SchedulerStopped()))
        else:
            self._tasks.append(task)
            self._reschedule()


    def _removeTask(self, task):
        """
        Remove a L{CooperativeTask} from this L{Cooperator}.
        """
        self._tasks.remove(task)
        # If no work left to do, cancel the delayed call:
        if not self._tasks and self._delayedCall:
            self._delayedCall.cancel()
            self._delayedCall = None


    def _tasksWhileNotStopped(self):
        """
        Yield all L{CooperativeTask} objects in a loop as long as this
        L{Cooperator}'s termination condition has not been met.
        """
        terminator = self._terminationPredicateFactory()
        while self._tasks:
            for t in self._metarator:
                yield t
                if terminator():
                    return
            self._metarator = iter(self._tasks)


    def _tick(self):
        """
        Run one scheduler tick.
        """
        self._delayedCall = None
        for taskObj in self._tasksWhileNotStopped():
            taskObj._oneWorkUnit()
        self._reschedule()


    _mustScheduleOnStart = False
    def _reschedule(self):
        if not self._started:
            self._mustScheduleOnStart = True
            return
        if self._delayedCall is None and self._tasks:
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
        for taskObj in self._tasks:
            taskObj._completeWith(SchedulerStopped(),
                                  Failure(SchedulerStopped()))
        self._tasks = []
        if self._delayedCall is not None:
            self._delayedCall.cancel()
            self._delayedCall = None



_theCooperator = Cooperator()

def coiterate(iterator):
    """
    Cooperatively iterate over the given iterator, dividing runtime between it
    and all other iterators which have been passed to this function and not yet
    exhausted.

    @param iterator: the iterator to invoke.

    @return: a Deferred that will fire when the iterator finishes.
    """
    return _theCooperator.coiterate(iterator)



def cooperate(iterator):
    """
    Start running the given iterator as a long-running cooperative task, by
    calling next() on it as a periodic timed event.

    @param iterator: the iterator to invoke.

    @return: a L{CooperativeTask} object representing this task.
    """
    return _theCooperator.cooperate(iterator)



@implementer(IReactorTime)
class Clock:
    """
    Provide a deterministic, easily-controlled implementation of
    L{IReactorTime.callLater}.  This is commonly useful for writing
    deterministic unit tests for code which schedules events using this API.
    """

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


    def _sortCalls(self):
        """
        Sort the pending calls according to the time they are scheduled.
        """
        self.calls.sort(key=lambda a: a.getTime())


    def callLater(self, when, what, *a, **kw):
        """
        See L{twisted.internet.interfaces.IReactorTime.callLater}.
        """
        dc = base.DelayedCall(self.seconds() + when,
                               what, a, kw,
                               self.calls.remove,
                               lambda c: None,
                               self.seconds)
        self.calls.append(dc)
        self._sortCalls()
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
        self._sortCalls()
        while self.calls and self.calls[0].getTime() <= self.seconds():
            call = self.calls.pop(0)
            call.called = 1
            call.func(*call.args, **call.kw)
            self._sortCalls()


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
    def deferLaterCancel(deferred):
        delayedCall.cancel()
    d = defer.Deferred(deferLaterCancel)
    d.addCallback(lambda ignored: callable(*args, **kw))
    delayedCall = clock.callLater(delay, d.callback, None)
    return d



def react(main, argv, _reactor=None):
    """
    Call C{main} and run the reactor until the L{Deferred} it returns fires.

    This is intended as the way to start up an application with a well-defined
    completion condition.  Use it to write clients or one-off asynchronous
    operations.  Prefer this to calling C{reactor.run} directly, as this
    function will also:

      - Take care to call C{reactor.stop} once and only once, and at the right
        time.
      - Log any failures from the C{Deferred} returned by C{main}.
      - Exit the application when done, with exit code 0 in case of success and
        1 in case of failure. If C{main} fails with a C{SystemExit} error, the
        code returned is used.

    @param main: A callable which returns a L{Deferred}.  It should take as
        many arguments as there are elements in the list C{argv}.

    @param argv: A list of arguments to pass to C{main}.

    @param _reactor: An implementation detail to allow easier unit testing.  Do
        not supply this parameter.

    @since: 12.3
    """
    if _reactor is None:
        from twisted.internet import reactor as _reactor
    finished = main(_reactor, *argv)
    codes = [0]

    stopping = []
    _reactor.addSystemEventTrigger('before', 'shutdown', stopping.append, True)

    def stop(result, stopReactor):
        if stopReactor:
            try:
                _reactor.stop()
            except ReactorNotRunning:
                pass

        if isinstance(result, Failure):
            if result.check(SystemExit) is not None:
                code = result.value.code
            else:
                log.err(result, "main function encountered error")
                code = 1
            codes[0] = code

    def cbFinish(result):
        if stopping:
            stop(result, False)
        else:
            _reactor.callWhenRunning(stop, result, True)

    finished.addBoth(cbFinish)
    _reactor.run()
    sys.exit(codes[0])


__all__ = [
    'LoopingCall',

    'Clock',

    'SchedulerStopped', 'Cooperator', 'coiterate',

    'deferLater', 'react']
