
from select import EPOLLET, EPOLLERR, EPOLLHUP, EPOLLIN, EPOLLOUT, EPOLLONESHOT, epoll
from time import time
from os import read, write, pipe, close

import transaction

from zope.interface import implements

import timerfd

from twisted.internet.interfaces import IReactorCore, IReactorFDSet, IHalfCloseableDescriptor, IReactorTCP
from twisted.internet import error, fdesc, tcp

from twisted.internet.main import installReactor
from twisted.internet.base import _ThreePhaseEvent, ThreadedResolver
from twisted.internet.abstract import isIPAddress
from twisted.internet.defer import succeed
from twisted.internet.task import Clock
from twisted.internet.error import (
    ReactorNotRunning, ReactorAlreadyRunning, ReactorNotRestartable,
    ConnectionLost, ConnectionDone, )
from twisted.python.constants import NamedConstant, Names
from twisted.python import failure

from twisted.internet.posixbase import _PollLikeMixin

class _StopReactor(Exception):
    pass



class _CrashReactor(Exception):
    pass



class _ReactorState(Names):
    # First state
    STOPPED = NamedConstant()

    # Entered after reactor.run()
    STARTING = NamedConstant()

    # Entered after last before startup trigger - by DURING_STARTUP
    READY = NamedConstant()

    # Entered after last during startup trigger - by STARTUP_COMPLETE
    RUNNING = NamedConstant()

    # Entered after reactor.crash() - by CRASH
    CRASHING = NamedConstant()

    # Entered after reactor.stop() - by STOP
    STOPPING = NamedConstant()

    # Entered after event loop really stops due to stop
    STOPPED_AND_RAN_ALREADY = NamedConstant()

    # Entered after event loop really stops due to crash
    CRASHED = NamedConstant()



class _StateInputs(Names):
    RUN = NamedConstant()
    DURING_STARTUP = NamedConstant()
    STARTUP_COMPLETE = NamedConstant()
    STOP = NamedConstant()
    CRASH = NamedConstant()



class _StateMachine(object):
    states = {
        _ReactorState.STOPPED: {
            _StateInputs.RUN: _ReactorState.STARTING,
            _StateInputs.STOP: ReactorNotRunning,
            _StateInputs.CRASH: ReactorNotRunning,
            },

        _ReactorState.CRASHED: {
            _StateInputs.RUN: _ReactorState.STARTING,
            _StateInputs.STOP: ReactorNotRunning,
            _StateInputs.CRASH: ReactorNotRunning,
            },

        _ReactorState.STARTING: {
            _StateInputs.RUN: ReactorAlreadyRunning,
            _StateInputs.DURING_STARTUP: _ReactorState.READY,
            _StateInputs.STOP: _ReactorState.STARTING,
            # XXX This is wrong, it'll go through normal reactor shutdown
            # but no unit tests fail
            _StateInputs.CRASH: _ReactorState.STARTING,
            },

        _ReactorState.READY: {
            _StateInputs.RUN: ReactorAlreadyRunning,
            _StateInputs.STARTUP_COMPLETE: _ReactorState.RUNNING,
            _StateInputs.STOP: _ReactorState.READY,
            _StateInputs.CRASH: _ReactorState.CRASHING,
            },

        _ReactorState.RUNNING: {
            _StateInputs.RUN: ReactorAlreadyRunning,
            _StateInputs.STOP: _ReactorState.STOPPING,
            _StateInputs.CRASH: _ReactorState.CRASHING,
            },

        _ReactorState.CRASHING: {
            _StateInputs.RUN: _ReactorState.CRASHING,
            _StateInputs.STARTUP_COMPLETE: _ReactorState.CRASHED,
            _StateInputs.CRASH: _ReactorState.CRASHING,
            },

        _ReactorState.STOPPING: {
            _StateInputs.RUN: ReactorNotRestartable,
            _StateInputs.STARTUP_COMPLETE: _ReactorState.STOPPING,
            _StateInputs.STOP: ReactorNotRunning,
            },

        _ReactorState.STOPPED_AND_RAN_ALREADY: {
            _StateInputs.RUN: ReactorNotRestartable,
            _StateInputs.STOP: ReactorNotRunning,
            _StateInputs.CRASH: ReactorNotRunning,
            },
        }

class _Waker(object):
    # implements(IFileDescriptor)

    def __init__(self, callback):
        self._r, self._w = pipe()
        for f in fdesc.setNonBlocking, fdesc._setCloseOnExec:
            for d in self._w, self._r:
                f(d)
        self._callback = callback
        print 'waker for', callback, 'is', self._r


    def fileno(self):
        return self._r


    def wake(self):
        try:
            write(self._w, 'x')
        except IOError, e:
            if e.errno != EAGAIN:
                raise


    def doRead(self):
        print 'firing', self._callback
        read(self._r, 1024)
        self._callback()
        print '------- did it'

    def connectionLost(self, reason):
        close(self._r)
        close(self._w)


class _TimerFD(object):
    # implements(IFileDescriptor)

    def __init__(self, callback):
        self._timerfd = timerfd.create(
            timerfd.CLOCK_MONOTONIC, timerfd.CLOEXEC | timerfd.NONBLOCK)
        self._callback = callback


    def _settimeout(self, delay):
        offset = max(0.0000001, delay)
        targetTime = timerfd.itimerspec(0, offset)
        timerfd.settime(self._timerfd, 0, targetTime)


    def fileno(self):
        return self._timerfd


    def doRead(self):
        read(self._timerfd, 100000)
        self._callback()


    def connectionLost(self, reason):
        close(self._timerfd)



class _DescriptorState(object):
    def __init__(self, reactor, fd, descr, flags):
        self.reactor = reactor
        self.fd = fd
        self.descr = descr
        self.kernelFlags = 0
        self.logicalFlags = flags


    def shot(self):
        self.kernelFlags = 0


    def register(self):
        self.reactor._register(self.fd, self.logicalFlags)
        self.kernelFlags = self.logicalFlags


    def update(self):
        if self.kernelFlags != self.logicalFlags:
            self.reactor._modify(self.fd, self.logicalFlags)
            self.kernelFlags = self.logicalFlags



class EPollSTMReactor(_PollLikeMixin, Clock):
    implements(IReactorCore, IReactorFDSet, IReactorTCP)

    def __init__(self):
        Clock.__init__(self)
        self._state = _ReactorState.STOPPED
        self.resolver = ThreadedResolver(self)
        self._eventTriggers = {}
        # Tacos are delicious
        self._descriptors = {}
        self._working = set()
        self._timer = None
        self._stopWaker = None
        self._normalWaker = None

    # IReactorCore
    @property
    def running(self):
        # XXX The STOPPING case is not tested
        return self._state in (
            _ReactorState.READY, _ReactorState.RUNNING, _ReactorState.STOPPING)


    def run(self):
        self._transition(_StateInputs.RUN)


    def stop(self):
        self._transition(_StateInputs.STOP)


    _crashing = False
    def crash(self):
        # XXX
        self._crashing = True
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


    # IReactorFDSet
    def addReader(self, reader):
        self._add(reader, EPOLLIN)


    def removeReader(self, reader):
        self._remove(reader, EPOLLIN)


    def addWriter(self, writer):
        self._add(writer, EPOLLOUT)


    def removeWriter(self, writer):
        self._remove(writer, EPOLLOUT)


    def getReaders(self):
        return [
            d.descr for (fd, d)
            in self._descriptors.iteritems()
            if d.logicalFlags & EPOLLIN]


    def getWriters(self):
        return [
            d.descr for (fd, d)
            in self._descriptors.iteritems()
            if d.logicalFlags & EPOLLOUT]


    def removeAll(self):
        result = []
        internal = (self._timer, self._stopWaker, self._normalWaker)
        for (fd, descr) in self._descriptors.items():
            # XXX Maybe it's worth forgetting about these sometimes?
            if descr.logicalFlags and descr.descr not in internal:
                self.removeReader(descr.descr)
                self.removeWriter(descr.descr)
                result.append(descr.descr)
        return result


    # IReactorTCP
    def listenTCP(self, port, factory, backlog=50, interface=''):
        """@see: twisted.internet.interfaces.IReactorTCP.listenTCP
        """
        p = tcp.Port(port, factory, backlog, interface, self)
        p.startListening()
        return p


    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """@see: twisted.internet.interfaces.IReactorTCP.connectTCP
        """
        c = tcp.Connector(host, port, factory, timeout, bindAddress, self)
        c.connect()
        return c


    # Implementation details
    @property
    def _reads(self):
        return self.getReaders()


    def _add(self, descr, op):
        fd = descr.fileno()
        try:
            descriptor = self._descriptors[fd]
        except KeyError:
            descriptor = self._descriptors[fd] = _DescriptorState(
                self, fd, descr, op)
            descriptor.register()
        else:
            descriptor.logicalFlags |= op
        if descriptor not in self._working:
            descriptor.update()


    def _remove(self, descr, op):
        fd = descr.fileno()
        try:
            descriptor = self._descriptors[fd]
        except KeyError:
            for (probefd, probedescr) in self._descriptors.iteritems():
                if descr is probedescr:
                    del self._descriptors[probefd]
                    break
        else:
            descriptor.logicalFlags &= ~op
            if descriptor not in self._working:
                descriptor.update()


    def _transition_STARTING_to_READY(self):
        pass

    def _reallyStopRunning(self):
        transaction.add(self._doubleReallyPlusGoodRunningCease)


    def _doubleReallyPlusGoodRunningCease(self):
        self._stopEPoll()


    def _addEPoll(self):
        self._stopEPoll = transaction.add_epoll(self._epoll, self._epollCallback)


    _POLL_DISCONNECTED = EPOLLHUP | EPOLLERR
    _POLL_IN = EPOLLIN
    _POLL_OUT = EPOLLOUT

    def _epollCallback(self, fd, events):
        descriptor = self._descriptors[fd]
        descriptor.shot()
        fileno = descriptor.descr.fileno()

        self._working.add(descriptor)
        try:
            self._doReadOrWrite(descriptor.descr, fd, events)
        finally:
            self._working.remove(descriptor)
            if fileno in self._descriptors:
                descriptor.update()


    def _disconnectSelectable(self, selectable, why, isRead, faildict={
        error.ConnectionDone: failure.Failure(error.ConnectionDone()),
        error.ConnectionLost: failure.Failure(error.ConnectionLost())
        }):
        """
        Utility function for disconnecting a selectable.

        Supports half-close notification, isRead should be boolean indicating
        whether error resulted from doRead().
        """
        self.removeReader(selectable)
        f = faildict.get(why.__class__)
        if f:
            if (isRead and why.__class__ ==  error.ConnectionDone
                and IHalfCloseableDescriptor.providedBy(selectable)):
                selectable.readConnectionLost(f)
            else:
                self.removeWriter(selectable)
                selectable.connectionLost(f)
        else:
            self.removeWriter(selectable)
            selectable.connectionLost(failure.Failure(why))


    def _addExisting(self):
        assert self._state in (_ReactorState.RUNNING, _ReactorState.STOPPING), "state is %r" % (self._state)
        for fd, descriptor in self._descriptors.iteritems():
            descriptor.register()


    def _register(self, fd, flags):
        if self._state in (_ReactorState.RUNNING, _ReactorState.STOPPING):
            self._epoll.register(fd, flags | EPOLLONESHOT)


    def _modify(self, fd, flags):
        if self._state in (_ReactorState.RUNNING, _ReactorState.STOPPING):
            self._epoll.modify(fd, flags | EPOLLONESHOT)


    def _startupDelayedCalls(self):
        self._timer = _TimerFD(self._runUntilCurrent)
        self.addReader(self._timer)
        self._rescheduleDelayedCalls()


    def _rescheduleDelayedCalls(self):
        calls = self.getDelayedCalls()
        if calls:
            self._timer._settimeout(calls[0].getTime() - self.seconds())


    def _startupControlPipes(self):
        self._stopWaker = _Waker(self._endEPoll)
        self.addReader(self._stopWaker)
        self._normalWaker = _Waker(lambda: None)
        self.addReader(self._normalWaker)


    def _endEPoll(self):
        self._stopEPoll()
        self._normalWaker.wake()


    def _runUntilCurrent(self):
        self.advance(self.seconds() - self.rightNow)
        self._rescheduleDelayedCalls()


    # State transition magic
    def _transition(self, input):
        oldState = self._state
        try:
            newState = _StateMachine.states[oldState][input]
        except KeyError, e:
            print 'illegal transition', oldState, input, e
            raise

        print 'Going from', oldState, 'to', newState, 'because', input
        try:
            isitsubclass = issubclass(newState, Exception)
        except TypeError:
            isitsubclass = False
        if isitsubclass:
            raise newState("Cannot handle %r in %r" % (input, oldState.name))
        self._state = newState
        getattr(self, '_transition_%s_to_%s' % (oldState.name, newState.name))()

    def _reallyStartRunning(self):
        self._transition(_StateInputs.DURING_STARTUP)

    def _transition_STOPPED_to_STARTING(self):
        self.addSystemEventTrigger(
            'before', 'startup', self._reallyStartRunning)
        self.addSystemEventTrigger(
            'after', 'shutdown', self._reallyStopRunning)

        self._startupControlPipes()
        self._startupDelayedCalls()

        self.fireSystemEvent('startup')
        self._transition(_StateInputs.STARTUP_COMPLETE)

    _transition_CRASHED_to_STARTING = _transition_STOPPED_to_STARTING

    def _transition_READY_to_READY(self):
        self._stopWaker.wake()


    def _transition_READY_to_CRASHING(self):
        self._stopWaker.wake()

    def _transition_STARTING_to_STARTING(self):
        self._stopWaker.wake()

    def _transition_READY_to_RUNNING(self):
        self._epoll = epoll()
        self._addEPoll()
        self._addExisting()
        self._rescheduleDelayedCalls()

        transaction.run()
        if self._crashing:
            self._state = _ReactorState.CRASHED
        else:
            self._state = _ReactorState.STOPPING
            self.fireSystemEvent('shutdown')
            transaction.run()
            self._state = _ReactorState.STOPPED_AND_RAN_ALREADY

        # if self._state is _ReactorState.STOPPING:
        #     self.fireSystemEvent('shutdown')
        #     transaction.run()
        #     self._state = _ReactorState.STOPPED_AND_RAN_ALREADY
        # elif self._state is _ReactorState.CRASHING:
        #     self._state = _ReactorState.CRASHED
        # else:
        #     assert False, "what" + str(self._state)

    def _transition_RUNNING_to_STOPPING(self):
        self._stopWaker.wake()

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
