# -*- test-case-name: twisted.test.test_internet -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Very basic functionality for a Reactor implementation.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import socket # needed only for sync-dns
from zope.interface import implements, classImplements

import imp
import sys
import warnings
import operator
from heapq import heappush, heappop, heapreplace, heapify

try:
    import fcntl
except ImportError:
    fcntl = None
import traceback

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorThreads
from twisted.internet.interfaces import IResolverSimple, IReactorPluggableResolver
from twisted.internet.interfaces import IConnector, IDelayedCall
from twisted.internet import main, error, abstract, defer, threads
from twisted.python import log, failure, reflect, components
from twisted.python.runtime import seconds, platform
from twisted.internet.defer import Deferred, DeferredList
from twisted.persisted import styles

# This import is for side-effects!  Even if you don't see any code using it
# in this module, don't delete it.
from twisted.python import threadable

class DelayedCall(styles.Ephemeral):

    implements(IDelayedCall)
    # enable .debug to record creator call stack, and it will be logged if
    # an exception occurs while the function is being run
    debug = False
    _str = None

    def __init__(self, time, func, args, kw, cancel, reset, seconds=None):
        """
        @param time: Seconds from the epoch at which to call C{func}.
        @param func: The callable to call.
        @param args: The positional arguments to pass to the callable.
        @param kw: The keyword arguments to pass to the callable.
        @param cancel: A callable which will be called with this
            DelayedCall before cancellation.
        @param reset: A callable which will be called with this
            DelayedCall after changing this DelayedCall's scheduled
            execution time. The callable should adjust any necessary
            scheduling details to ensure this DelayedCall is invoked
            at the new appropriate time.
        @param seconds: If provided, a no-argument callable which will be
            used to determine the current time any time that information is
            needed.
        """
        self.time, self.func, self.args, self.kw = time, func, args, kw
        self.resetter = reset
        self.canceller = cancel
        self.seconds = seconds
        self.cancelled = self.called = 0
        self.delayed_time = 0
        if self.debug:
            self.creator = traceback.format_stack()[:-2]

    def getTime(self):
        """Return the time at which this call will fire

        @rtype: C{float}
        @return: The number of seconds after the epoch at which this call is
        scheduled to be made.
        """
        return self.time + self.delayed_time

    def cancel(self):
        """Unschedule this call

        @raise AlreadyCancelled: Raised if this call has already been
        unscheduled.

        @raise AlreadyCalled: Raised if this call has already been made.
        """
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.canceller(self)
            self.cancelled = 1
            if self.debug:
                self._str = str(self)
            del self.func, self.args, self.kw

    def reset(self, secondsFromNow):
        """Reschedule this call for a different time

        @type secondsFromNow: C{float}
        @param secondsFromNow: The number of seconds from the time of the
        C{reset} call at which this call will be scheduled.

        @raise AlreadyCancelled: Raised if this call has been cancelled.
        @raise AlreadyCalled: Raised if this call has already been made.
        """
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            if self.seconds is None:
                new_time = seconds() + secondsFromNow
            else:
                new_time = self.seconds() + secondsFromNow
            if new_time < self.time:
                self.delayed_time = 0
                self.time = new_time
                self.resetter(self)
            else:
                self.delayed_time = new_time - self.time

    def delay(self, secondsLater):
        """Reschedule this call for a later time

        @type secondsLater: C{float}
        @param secondsLater: The number of seconds after the originally
        scheduled time for which to reschedule this call.

        @raise AlreadyCancelled: Raised if this call has been cancelled.
        @raise AlreadyCalled: Raised if this call has already been made.
        """
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.delayed_time += secondsLater
            if self.delayed_time < 0:
                self.activate_delay()
                self.resetter(self)

    def activate_delay(self):
        self.time += self.delayed_time
        self.delayed_time = 0

    def active(self):
        """Determine whether this call is still pending

        @rtype: C{bool}
        @return: True if this call has not yet been made or cancelled,
        False otherwise.
        """
        return not (self.cancelled or self.called)

    def __le__(self, other):
        return self.time <= other.time

    def __str__(self):
        if self._str is not None:
            return self._str
        if hasattr(self, 'func'):
            if hasattr(self.func, 'func_name'):
                func = self.func.func_name
                if hasattr(self.func, 'im_class'):
                    func = self.func.im_class.__name__ + '.' + func
            else:
                func = reflect.safe_repr(self.func)
        else:
            func = None

        if self.seconds is None:
            now = seconds()
        else:
            now = self.seconds()
        L = ["<DelayedCall %s [%ss] called=%s cancelled=%s" % (
                id(self), self.time - now, self.called, self.cancelled)]
        if func is not None:
            L.extend((" ", func, "("))
            if self.args:
                L.append(", ".join([reflect.safe_repr(e) for e in self.args]))
                if self.kw:
                    L.append(", ")
            if self.kw:
                L.append(", ".join(['%s=%s' % (k, reflect.safe_repr(v)) for (k, v) in self.kw.iteritems()]))
            L.append(")")

        if self.debug:
            L.append("\n\ntraceback at creation: \n\n%s" % ('    '.join(self.creator)))
        L.append('>')

        return "".join(L)


class ThreadedResolver:
    implements(IResolverSimple)

    def __init__(self, reactor):
        self.reactor = reactor
        self._runningQueries = {}

    def _fail(self, name, err):
        err = error.DNSLookupError("address %r not found: %s" % (name, err))
        return failure.Failure(err)

    def _cleanup(self, name, lookupDeferred):
        userDeferred, cancelCall = self._runningQueries[lookupDeferred]
        del self._runningQueries[lookupDeferred]
        userDeferred.errback(self._fail(name, "timeout error"))

    def _checkTimeout(self, result, name, lookupDeferred):
        try:
            userDeferred, cancelCall = self._runningQueries[lookupDeferred]
        except KeyError:
            pass
        else:
            del self._runningQueries[lookupDeferred]
            cancelCall.cancel()

            if isinstance(result, failure.Failure):
                userDeferred.errback(self._fail(name, result.getErrorMessage()))
            else:
                userDeferred.callback(result)

    def getHostByName(self, name, timeout = (1, 3, 11, 45)):
        if timeout:
            timeoutDelay = reduce(operator.add, timeout)
        else:
            timeoutDelay = 60
        userDeferred = defer.Deferred()
        lookupDeferred = threads.deferToThread(socket.gethostbyname, name)
        cancelCall = self.reactor.callLater(
            timeoutDelay, self._cleanup, name, lookupDeferred)
        self._runningQueries[lookupDeferred] = (userDeferred, cancelCall)
        lookupDeferred.addBoth(self._checkTimeout, name, lookupDeferred)
        return userDeferred

class BlockingResolver:
    implements(IResolverSimple)

    def getHostByName(self, name, timeout = (1, 3, 11, 45)):
        try:
            address = socket.gethostbyname(name)
        except socket.error:
            msg = "address %r not found" % (name,)
            err = error.DNSLookupError(msg)
            return defer.fail(err)
        else:
            return defer.succeed(address)

class ReactorBase(object):
    """Default base class for Reactors.
    """

    implements(IReactorCore, IReactorTime, IReactorPluggableResolver)

    installed = 0
    usingThreads = 0
    resolver = BlockingResolver()

    __name__ = "twisted.internet.reactor"

    def __init__(self):
        self.threadCallQueue = []
        self._eventTriggers = {}
        self._pendingTimedCalls = []
        self._newTimedCalls = []
        self._cancellations = 0
        self.running = 0
        self.waker = None

        self.addSystemEventTrigger('during', 'shutdown', self.crash)
        self.addSystemEventTrigger('during', 'shutdown', self.disconnectAll)

        if platform.supportsThreads():
            self._initThreads()

    # override in subclasses

    _lock = None

    def installWaker(self):
        raise NotImplementedError()

    def installResolver(self, resolver):
        assert IResolverSimple.providedBy(resolver)
        oldResolver = self.resolver
        self.resolver = resolver
        return oldResolver

    def wakeUp(self):
        """Wake up the event loop."""
        if not threadable.isInIOThread():
            if self.waker:
                self.waker.wakeUp()
            # if the waker isn't installed, the reactor isn't running, and
            # therefore doesn't need to be woken up

    def doIteration(self, delay):
        """Do one iteration over the readers and writers we know about."""
        raise NotImplementedError

    def addReader(self, reader):
        raise NotImplementedError

    def addWriter(self, writer):
        raise NotImplementedError

    def removeReader(self, reader):
        raise NotImplementedError

    def removeWriter(self, writer):
        raise NotImplementedError

    def removeAll(self):
        raise NotImplementedError

    def resolve(self, name, timeout = (1, 3, 11, 45)):
        """Return a Deferred that will resolve a hostname.
        """
        if not name:
            # XXX - This is *less than* '::', and will screw up IPv6 servers
            return defer.succeed('0.0.0.0')
        if abstract.isIPAddress(name):
            return defer.succeed(name)
        return self.resolver.getHostByName(name, timeout)

    # Installation.

    # IReactorCore

    def stop(self):
        """See twisted.internet.interfaces.IReactorCore.stop.
        """
        if not self.running:
            raise RuntimeError, "can't stop reactor that isn't running"
        self.fireSystemEvent("shutdown")

    def crash(self):
        """See twisted.internet.interfaces.IReactorCore.crash.
        """
        self.running = 0

    def sigInt(self, *args):
        """Handle a SIGINT interrupt.
        """
        log.msg("Received SIGINT, shutting down.")
        self.callFromThread(self.stop)

    def sigBreak(self, *args):
        """Handle a SIGBREAK interrupt.
        """
        log.msg("Received SIGBREAK, shutting down.")
        self.callFromThread(self.stop)

    def sigTerm(self, *args):
        """Handle a SIGTERM interrupt.
        """
        log.msg("Received SIGTERM, shutting down.")
        self.callFromThread(self.stop)

    def disconnectAll(self):
        """Disconnect every reader, and writer in the system.
        """
        selectables = self.removeAll()
        for reader in selectables:
            log.callWithLogger(reader,
                               reader.connectionLost,
                               failure.Failure(main.CONNECTION_LOST))


    def iterate(self, delay=0):
        """See twisted.internet.interfaces.IReactorCore.iterate.
        """
        self.runUntilCurrent()
        self.doIteration(delay)

    def fireSystemEvent(self, eventType):
        """See twisted.internet.interfaces.IReactorCore.fireSystemEvent.
        """
        sysEvtTriggers = self._eventTriggers.get(eventType)
        if not sysEvtTriggers:
            return
        defrList = []
        for callable, args, kw in sysEvtTriggers[0]:
            try:
                d = callable(*args, **kw)
            except:
                log.deferr()
            else:
                if isinstance(d, Deferred):
                    defrList.append(d)
        if defrList:
            DeferredList(defrList).addBoth(self._cbContinueSystemEvent, eventType)
        else:
            self.callLater(0, self._continueSystemEvent, eventType)


    def _cbContinueSystemEvent(self, result, eventType):
        self._continueSystemEvent(eventType)


    def _continueSystemEvent(self, eventType):
        sysEvtTriggers = self._eventTriggers.get(eventType)
        for callList in sysEvtTriggers[1], sysEvtTriggers[2]:
            for callable, args, kw in callList:
                try:
                    callable(*args, **kw)
                except:
                    log.deferr()
        # now that we've called all callbacks, no need to store
        # references to them anymore, in fact this can cause problems.
        del self._eventTriggers[eventType]

    def addSystemEventTrigger(self, _phase, _eventType, _f, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.addSystemEventTrigger.
        """
        assert callable(_f), "%s is not callable" % _f
        if self._eventTriggers.has_key(_eventType):
            triglist = self._eventTriggers[_eventType]
        else:
            triglist = [[], [], []]
            self._eventTriggers[_eventType] = triglist
        evtList = triglist[{"before": 0, "during": 1, "after": 2}[_phase]]
        evtList.append((_f, args, kw))
        return (_phase, _eventType, (_f, args, kw))

    def removeSystemEventTrigger(self, triggerID):
        """See twisted.internet.interfaces.IReactorCore.removeSystemEventTrigger.
        """
        phase, eventType, item = triggerID
        self._eventTriggers[eventType][{"before": 0,
                                        "during": 1,
                                        "after":  2}[phase]
                                       ].remove(item)

    def callWhenRunning(self, _callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.callWhenRunning.
        """
        if self.running:
            _callable(*args, **kw)
        else:
            return self.addSystemEventTrigger('after', 'startup',
                                              _callable, *args, **kw)

    # IReactorTime

    def callLater(self, _seconds, _f, *args, **kw):
        """See twisted.internet.interfaces.IReactorTime.callLater.
        """
        assert callable(_f), "%s is not callable" % _f
        assert sys.maxint >= _seconds >= 0, \
               "%s is not greater than or equal to 0 seconds" % (_seconds,)
        tple = DelayedCall(seconds() + _seconds, _f, args, kw,
                           self._cancelCallLater,
                           self._moveCallLaterSooner)
        self._newTimedCalls.append(tple)
        return tple

    def _moveCallLaterSooner(self, tple):
        # Linear time find: slow.
        heap = self._pendingTimedCalls
        try:
            pos = heap.index(tple)

            # Move elt up the heap until it rests at the right place.
            elt = heap[pos]
            while pos != 0:
                parent = (pos-1) // 2
                if heap[parent] <= elt:
                    break
                # move parent down
                heap[pos] = heap[parent]
                pos = parent
            heap[pos] = elt
        except ValueError:
            # element was not found in heap - oh well...
            pass

    def _cancelCallLater(self, tple):
        self._cancellations+=1

    def cancelCallLater(self, callID):
        """See twisted.internet.interfaces.IReactorTime.cancelCallLater.
        """
        # DO NOT DELETE THIS - this is documented in Python in a Nutshell, so we
        # we can't get rid of it for a long time.
        warnings.warn("reactor.cancelCallLater(callID) is deprecated - use callID.cancel() instead")
        callID.cancel()

    def getDelayedCalls(self):
        """Return all the outstanding delayed calls in the system.
        They are returned in no particular order.
        This method is not efficient -- it is really only meant for
        test cases."""
        return [x for x in (self._pendingTimedCalls + self._newTimedCalls) if not x.cancelled]

    def _insertNewDelayedCalls(self):
        for call in self._newTimedCalls:
            if call.cancelled:
                self._cancellations-=1
            else:
                call.activate_delay()
                heappush(self._pendingTimedCalls, call)
        self._newTimedCalls = []

    def timeout(self):
        # insert new delayed calls to make sure to include them in timeout value
        self._insertNewDelayedCalls()

        if not self._pendingTimedCalls:
            return None

        return max(0, self._pendingTimedCalls[0].time - seconds())

    def runUntilCurrent(self):
        """Run all pending timed calls.
        """
        if self.threadCallQueue:
            # Keep track of how many calls we actually make, as we're
            # making them, in case another call is added to the queue
            # while we're in this loop.
            count = 0
            for (f, a, kw) in self.threadCallQueue:
                try:
                    f(*a, **kw)
                except:
                    log.err()
                count += 1
            del self.threadCallQueue[:count]

        # insert new delayed calls now
        self._insertNewDelayedCalls()

        now = seconds()
        while self._pendingTimedCalls and (self._pendingTimedCalls[0].time <= now):
            call = heappop(self._pendingTimedCalls)
            if call.cancelled:
                self._cancellations-=1
                continue

            if call.delayed_time > 0:
                call.activate_delay()
                heappush(self._pendingTimedCalls, call)
                continue

            try:
                call.called = 1
                call.func(*call.args, **call.kw)
            except:
                log.deferr()
                if hasattr(call, "creator"):
                    e = "\n"
                    e += " C: previous exception occurred in " + \
                         "a DelayedCall created here:\n"
                    e += " C:"
                    e += "".join(call.creator).rstrip().replace("\n","\n C:")
                    e += "\n"
                    log.msg(e)


        if (self._cancellations > 50 and
             self._cancellations > len(self._pendingTimedCalls) >> 1):
            self._cancellations = 0
            self._pendingTimedCalls = [x for x in self._pendingTimedCalls
                                       if not x.cancelled]
            heapify(self._pendingTimedCalls)

    # IReactorThreads
    if platform.supportsThreads():
        threadpool = None

        def _initThreads(self):
            self.usingThreads = 1
            self.resolver = ThreadedResolver(self)
            self.installWaker()

        def callFromThread(self, f, *args, **kw):
            """See twisted.internet.interfaces.IReactorThreads.callFromThread.
            """
            assert callable(f), "%s is not callable" % (f,)
            # lists are thread-safe in CPython, but not in Jython
            # this is probably a bug in Jython, but until fixed this code
            # won't work in Jython.
            self.threadCallQueue.append((f, args, kw))
            self.wakeUp()

        def _initThreadPool(self):
            from twisted.python import threadpool
            self.threadpool = threadpool.ThreadPool(0, 10, 'twisted.internet.reactor')
            self.callWhenRunning(self.threadpool.start)
            self.addSystemEventTrigger('during', 'shutdown', self.threadpool.stop)

        def callInThread(self, _callable, *args, **kwargs):
            """See twisted.internet.interfaces.IReactorThreads.callInThread.
            """
            if self.threadpool is None:
                self._initThreadPool()
            self.threadpool.callInThread(_callable, *args, **kwargs)

        def suggestThreadPoolSize(self, size):
            """See twisted.internet.interfaces.IReactorThreads.suggestThreadPoolSize.
            """
            if size == 0 and not self.threadpool:
                return
            if not self.threadpool:
                self._initThreadPool()
            self.threadpool.adjustPoolsize(maxthreads=size)
    else:
        # This is for signal handlers.
        def callFromThread(self, f, *args, **kw):
            assert callable(f), "%s is not callable" % (f,)
            # See comment in the other callFromThread implementation.
            self.threadCallQueue.append((f, args, kw))

if platform.supportsThreads():
    classImplements(ReactorBase, IReactorThreads)


class BaseConnector(styles.Ephemeral):
    """Basic implementation of connector.

    State can be: "connecting", "connected", "disconnected"
    """

    implements(IConnector)

    timeoutID = None
    factoryStarted = 0

    def __init__(self, factory, timeout, reactor):
        self.state = "disconnected"
        self.reactor = reactor
        self.factory = factory
        self.timeout = timeout

    def disconnect(self):
        """Disconnect whatever our state is."""
        if self.state == 'connecting':
            self.stopConnecting()
        elif self.state == 'connected':
            self.transport.loseConnection()

    def connect(self):
        """Start connection to remote server."""
        if self.state != "disconnected":
            raise RuntimeError, "can't connect in this state"

        self.state = "connecting"
        if not self.factoryStarted:
            self.factory.doStart()
            self.factoryStarted = 1
        self.transport = transport = self._makeTransport()
        if self.timeout is not None:
            self.timeoutID = self.reactor.callLater(self.timeout, transport.failIfNotConnected, error.TimeoutError())
        self.factory.startedConnecting(self)

    def stopConnecting(self):
        """Stop attempting to connect."""
        if self.state != "connecting":
            raise error.NotConnectingError, "we're not trying to connect"

        self.state = "disconnected"
        self.transport.failIfNotConnected(error.UserError())
        del self.transport

    def cancelTimeout(self):
        if self.timeoutID is not None:
            try:
                self.timeoutID.cancel()
            except ValueError:
                pass
            del self.timeoutID

    def buildProtocol(self, addr):
        self.state = "connected"
        self.cancelTimeout()
        return self.factory.buildProtocol(addr)

    def connectionFailed(self, reason):
        self.cancelTimeout()
        self.transport = None
        self.state = "disconnected"
        self.factory.clientConnectionFailed(self, reason)
        if self.state == "disconnected":
            # factory hasn't called our connect() method
            self.factory.doStop()
            self.factoryStarted = 0

    def connectionLost(self, reason):
        self.state = "disconnected"
        self.factory.clientConnectionLost(self, reason)
        if self.state == "disconnected":
            # factory hasn't called our connect() method
            self.factory.doStop()
            self.factoryStarted = 0

    def getDestination(self):
        raise NotImplementedError, "implement in subclasses"


class BasePort(abstract.FileDescriptor):
    """Basic implementation of a ListeningPort.

    Note: This does not actually implement IListeningPort.
    """

    addressFamily = None
    socketType = None

    def createInternetSocket(self):
        s = socket.socket(self.addressFamily, self.socketType)
        s.setblocking(0)
        if fcntl and hasattr(fcntl, 'FD_CLOEXEC'):
            old = fcntl.fcntl(s.fileno(), fcntl.F_GETFD)
            fcntl.fcntl(s.fileno(), fcntl.F_SETFD, old | fcntl.FD_CLOEXEC)
        return s


    def doWrite(self):
        """Raises a RuntimeError"""
        raise RuntimeError, "doWrite called on a %s" % reflect.qual(self.__class__)


__all__ = []
