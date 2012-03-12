
from select import EPOLLIN, epoll
from time import time
from os import write, pipe

import transaction

from zope.interface import implements

import timerfd

from twisted.internet.interfaces import IReactorCore

from twisted.internet.main import installReactor
from twisted.internet.base import _ThreePhaseEvent, ThreadedResolver
from twisted.internet.abstract import isIPAddress
from twisted.internet.defer import succeed
from twisted.internet.task import Clock
from twisted.internet.error import ReactorNotRunning, ReactorAlreadyRunning, ReactorNotRestartable
from twisted.python.constants import NamedConstant, Names

class _StopReactor(Exception):
    pass

class _CrashReactor(Exception):
    pass


class _ReactorState(Names):
    STOPPED = NamedConstant()
    STARTING = NamedConstant()
    READY = NamedConstant()
    RUNNING = NamedConstant()
    CRASHING = NamedConstant()
    STOPPING = NamedConstant()
    STOPPED_AND_RAN_ALREADY = NamedConstant()
    CRASHED = NamedConstant()



class _StateInputs(Names):
    RUN = NamedConstant()
    STARTUP_COMPLETE = NamedConstant()
    STOP = NamedConstant()
    CRASH = NamedConstant()



class _StateMachine(object):
    states = {
        _ReactorState.STOPPED: {
            _StateInputs.RUN: _ReactorState.STARTING,
            _StateInputs.STARTUP_COMPLETE: RuntimeError,
            _StateInputs.STOP: ReactorNotRunning,
            _StateInputs.CRASH: ReactorNotRunning,
            },

        _ReactorState.CRASHED: {
            _StateInputs.RUN: _ReactorState.STARTING,
            _StateInputs.STARTUP_COMPLETE: RuntimeError,
            _StateInputs.STOP: ReactorNotRunning,
            _StateInputs.CRASH: ReactorNotRunning,
            },

        _ReactorState.STARTING: {
            _StateInputs.RUN: ReactorAlreadyRunning,
            _StateInputs.STARTUP_COMPLETE: _ReactorState.READY,
            _StateInputs.STOP: _ReactorState.STARTING,
            # XXX This is wrong, it'll go through normal reactor shutdown
            # but no unit tests fail
            _StateInputs.CRASH: _ReactorState.STARTING,
            },

        _ReactorState.READY: {
            _StateInputs.RUN: ReactorAlreadyRunning,
            _StateInputs.STARTUP_COMPLETE: RuntimeError,
            # And _stopWritePipe here too
            _StateInputs.STOP: _ReactorState.STOPPING,
            _StateInputs.CRASH: _ReactorState.CRASHING,
            },

        _ReactorState.RUNNING: {
            _StateInputs.RUN: ReactorAlreadyRunning,
            _StateInputs.STARTUP_COMPLETE: RuntimeError,
            _StateInputs.STOP: _ReactorState.STOPPING,
            _StateInputs.CRASH: _ReactorState.CRASHING,
            },

        _ReactorState.CRASHING: {
            _StateInputs.RUN: _ReactorState.CRASHING,
            _StateInputs.STARTUP_COMPLETE: _ReactorState.CRASHED,
            _StateInputs.STOP: RuntimeError,
            _StateInputs.CRASH: _ReactorState.CRASHING,
            },

        _ReactorState.STOPPING: {
            _StateInputs.RUN: ReactorNotRestartable,
            _StateInputs.STARTUP_COMPLETE: _ReactorState.STOPPING,
            _StateInputs.STOP: ReactorNotRunning,
            _StateInputs.CRASH: RuntimeError,
            },

        _ReactorState.STOPPED_AND_RAN_ALREADY: {
            _StateInputs.RUN: ReactorNotRestartable,
            _StateInputs.STARTUP_COMPLETE: RuntimeError,
            _StateInputs.STOP: ReactorNotRunning,
            _StateInputs.CRASH: ReactorNotRunning,
            },
        }


class EPollSTMReactor(Clock):
    implements(IReactorCore)

    def __init__(self):
        Clock.__init__(self)
        self._state = _ReactorState.STOPPED
        self.resolver = ThreadedResolver(self)
        self._readers = {}
        self._eventTriggers = {}


    # IReactorCore
    @property
    def running(self):
        return self._state in (_ReactorState.READY, _ReactorState.RUNNING)


    def run(self):
        self._transition(_StateInputs.RUN)


    def stop(self):
        self._transition(_StateInputs.STOP)


    def crash(self):
        self._transition(_StateInputs.CRASH)


    def iterate(self, delay=0):
        raise NotImplementedError()


    def fireSystemEvent(self, eventType):
        """See twisted.internet.interfaces.IReactorCore.fireSystemEvent.
        """
        event = self._eventTriggers.get(eventType)
        if event is not None:
            event.fireEvent()


    def addSystemEventTrigger(self, _phase, _eventType, _f, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.addSystemEventTrigger.
        """
        assert callable(_f), "%s is not callable" % _f
        if _eventType not in self._eventTriggers:
            self._eventTriggers[_eventType] = _ThreePhaseEvent()
        return (_eventType, self._eventTriggers[_eventType].addTrigger(
            _phase, _f, *args, **kw))


    def removeSystemEventTrigger(self, triggerID):
        """See twisted.internet.interfaces.IReactorCore.removeSystemEventTrigger.
        """
        eventType, handle = triggerID
        self._eventTriggers[eventType].removeTrigger(handle)


    def callWhenRunning(self, _callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.callWhenRunning.
        """
        if self._state is _ReactorState.RUNNING:
            _callable(*args, **kw)
        else:
            return self.addSystemEventTrigger('after', 'startup',
                                              _callable, *args, **kw)


    def resolve(self, name, timeout=None):
        if not name:
            return succeed('0.0.0.0')
        if isIPAddress(name):
            return succeed(name)
        return self.resolver.getHostByName(name, timeout)


    # IReactorTime
    def seconds(self):
        return time()


    def callLater(self, *args, **kwargs):
        try:
            return Clock.callLater(self, *args, **kwargs)
        finally:
            if self._state in (_ReactorState.STARTING, _ReactorState.RUNNING):
                self._rescheduleDelayedCalls()


    # Implementation details
    def _reallyStartRunning(self):
        """
        Method called to transition to the running state.  This should happen
        in the I{during startup} event trigger phase.
        """
        self._transition(_StateInputs.STARTUP_COMPLETE)


    def _transition_STARTING_to_READY(self):
        pass

    def _reallyStopRunning(self):
        transaction.add(self._doubleReallyPlusGoodRunningCease)


    def _doubleReallyPlusGoodRunningCease(self):
        raise _StopReactor()


    def _addEPoll(self):
        transaction.add_epoll(self._epoll, self._doReadOrWrite)


    def _doReadOrWrite(self, fd, events):
        self._readers[fd]()


    def _addExisting(self):
        for r in self._readers:
            self._epoll.register(r, EPOLLIN)


    def _startupDelayedCalls(self):
        self._timerfd = timerfd.create(
            timerfd.CLOCK_MONOTONIC, timerfd.CLOEXEC | timerfd.NONBLOCK)
        self._rescheduleDelayedCalls()
        self._addReader(self._timerfd, self._runUntilCurrent)


    def _rescheduleDelayedCalls(self):
        calls = self.getDelayedCalls()
        if calls:
            offset = max(0.0000001, calls[0].getTime() - self.seconds())
            targetTime = timerfd.itimerspec(0, offset)
            timerfd.settime(self._timerfd, 0, targetTime)


    def _startupControlPipes(self):
        self._stopReadPipe, self._stopWritePipe = pipe()
        self._addReader(self._stopReadPipe, self._endEPoll)


    def _endEPoll(self):
        if self._state is _ReactorState.STOPPING:
            raise _StopReactor()
        elif self._state is _ReactorState.CRASHING:
            raise _CrashReactor()


    def _addReader(self, fd, handler):
        self._readers[fd] = handler
        if self._state is _ReactorState.RUNNING:
            self._epoll.register(fd, EPOLLIN | EPOLLONESHOT)


    def _runUntilCurrent(self):
        self.advance(self.seconds() - self.rightNow)
        self._rescheduleDelayedCalls()


    # State transition magic
    def _transition(self, input):
        oldState = self._state
        newState = _StateMachine.states[oldState][input]
        # print 'Going from', oldState, 'to', newState, 'because', input
        try:
            isitsubclass = issubclass(newState, Exception)
        except TypeError:
            isitsubclass = False
        if isitsubclass:
            raise newState("Cannot handle %r in %r" % (input, oldState.name))
        self._state = newState
        getattr(self, '_transition_%s_to_%s' % (oldState.name, newState.name))()


    def _transition_STOPPED_to_STARTING(self):
        self.addSystemEventTrigger(
            'before', 'startup', self._reallyStartRunning)
        self.addSystemEventTrigger(
            'after', 'shutdown', self._reallyStopRunning)

        self._startupControlPipes()
        self._startupDelayedCalls()

        self.fireSystemEvent('startup')
        self._transition_READY_to_RUNNING()

    _transition_CRASHED_to_STARTING = _transition_STOPPED_to_STARTING

    def _transition_READY_to_STOPPING(self):
        write(self._stopWritePipe, 'x')

    def _transition_READY_to_CRASHING(self):
        write(self._stopWritePipe, 'x')

    def _transition_STARTING_to_STARTING(self):
        write(self._stopWritePipe, 'x')

    def _transition_READY_to_RUNNING(self):
        self._epoll = epoll()
        self._addEPoll()
        self._addExisting()
        self._rescheduleDelayedCalls()

        try:
            transaction.run()
        except _StopReactor:
            self.fireSystemEvent('shutdown')
            try:
                transaction.run()
            except _StopReactor:
                pass
            self._state = _ReactorState.STOPPED_AND_RAN_ALREADY
        except _CrashReactor:
            self._state = _ReactorState.CRASHED

    def _transition_RUNNING_to_STOPPING(self):
        write(self._stopWritePipe, 'x')

    _transition_STARTING_to_STOPPING = _transition_RUNNING_to_STOPPING
    _transition_STARTING_to_CRASHING = _transition_RUNNING_to_STOPPING
    _transition_RUNNING_to_CRASHING = _transition_RUNNING_to_STOPPING


    def _transition_CRASHING_to_CRASHING(self):
        pass

    def _transition_CRASHING_to_CRASHED(self):
        pass

    def _transition_STOPPING_to_STOPPING(self):
        pass


def check():
    for (state, transitions) in _StateMachine.states.iteritems():
        for (input, newState) in transitions.iteritems():
            try:
                method = '_transition_%s_to_%s' % (state.name, newState.name)
            except AttributeError:
                assert issubclass(newState, Exception)
            else:
                assert getattr(EPollSTMReactor, method, None) is not None, "missing %s" % (method,)

check()

def install():
    installReactor(EPollSTMReactor())
