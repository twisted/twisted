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

"""Very basic functionality for a Reactor implementation.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import socket # needed only for sync-dns

import warnings
from time import time
from bisect import insort

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX, IReactorThreads
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL
from twisted.internet.interfaces import IReactorProcess
from twisted.internet import main, error
from twisted.python import threadable, log, failure, reflect
from twisted.internet.defer import Deferred, DeferredList


def _nmin(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)



class DelayedCall:
    def __init__(self, time, func, args, kw, cancel, reset):
        self.time, self.func, self.args, self.kw = time, func, args, kw
        self.resetter = reset
        self.canceller = cancel
        self.cancelled = self.called = 0

    def cancel(self):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.canceller(self)
            self.cancelled = 1

    def reset(self, secondsFromNow):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.time = time() + secondsFromNow
            self.resetter(self)

    def delay(self, secondsLater):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.time += secondsLater
            self.resetter(self)

    def __cmp__(self, other):
        if isinstance(other, DelayedCall):
            return cmp((self.time, self.func, self.args, self.kw), (other.time, other.func, other.args, other.kw))
        raise TypeError

    def __str__(self):
        try:
            func = self.func.func_name
            try:
                func = self.func.im_class.__name__ + '.' + func
            except:
                pass
        except:
            func = reflect.safe_repr(self.func)
        return "<DelayedCall [%ds] called=%s cancelled=%s %s%s>" % (self.time - time(), self.called, self.cancelled, func, reflect.safe_repr(self.args))

class ReactorBase:
    """Default base class for Reactors.
    """

    __implements__ = IReactorCore, IReactorTime, IReactorThreads
    installed = 0

    __name__ = "twisted.internet.reactor"

    def __init__(self):
        self._eventTriggers = {}
        self._pendingTimedCalls = []
        self._delayeds = main._delayeds
        self.waker = None
        self.usingThreads = 0
        self.addSystemEventTrigger('during', 'shutdown', self.crash)
        self.addSystemEventTrigger('during', 'shutdown', self.disconnectAll)
        threadable.whenThreaded(self.initThreads)

    # override in subclasses

    _lock = None

    def initThreads(self):
        import thread
        self.usingThreads = 1
        self.installWaker()
        self.threadCallQueue = []

    threadCallQueue = None

    def installWaker(self):
        raise NotImplementedError()

    def callFromThread(self, f, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.callFromThread.
        """
        assert callable(f), "%s is not callable" % f
        if threadable.isInIOThread():
            apply(self.callLater, (0, f)+ args, kw)
        else:
            # lists are thread-safe in CPython, but not in Jython
            # this is probably a bug in Jython, but until fixed this code
            # won't work in Jython.
            self.threadCallQueue.append((f, args, kw))
            self.wakeUp()

    def wakeUp(self):
        """Wake up the event loop."""
        if not threadable.isInIOThread():
            if self.waker:
                self.waker.wakeUp()
            # if the waker isn't installed, the reactor isn't running, and
            # therefore doesn't need to be woken up

    def doIteration(self):
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

    def resolve(self, name, type=1, timeout=10):
        """Return a Deferred that will resolve a hostname.
        """
        # XXX TODO: alternative resolver implementations
        from twisted.internet.defer import Deferred
        deferred = Deferred()
        if type == 1:
            try:
                address = socket.gethostbyname(name)
            except socket.error:
                deferred.errback(failure.Failure(error.DNSLookupError("address not found")))
            else:
                deferred.callback(address)
        else:
            deferred.errback(failure.Failure(ValueError("type not supported")))
        return deferred

    # Installation.

    # IReactorCore

    def stop(self):
        """See twisted.internet.interfaces.IReactorCore.stop.
        """
        self.fireSystemEvent("shutdown")

    def crash(self):
        """See twisted.internet.interfaces.IReactorCore.crash.
        """
        self.running = 0

    def sigInt(self, *args):
        """Handle a SIGINT interrupt.
        """
        self.callLater(0, self.stop)

    def sigBreak(self, *args):
        """Handle a SIGBREAK interrupt.
        """
        self.callLater(0, self.stop)

    def sigTerm(self, *args):
        """Handle a SIGTERM interrupt.
        """
        self.callLater(0, self.stop)

    def disconnectAll(self):
        """Disconnect every reader, and writer in the system.
        """
        selectables = self.removeAll()
        for reader in selectables:
            log.logOwner.own(reader)
            try:
                reader.connectionLost(failure.Failure(main.CONNECTION_LOST))
            except:
                log.deferr()
            log.logOwner.disown(reader)


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
                d = apply(callable, args, kw)
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
                    apply(callable, args, kw)
                except:
                    log.deferr()

    def addSystemEventTrigger(self, phase, eventType, f, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.addSystemEventTrigger.
        """
        assert callable(f)
        if self._eventTriggers.has_key(eventType):
            triglist = self._eventTriggers[eventType]
        else:
            triglist = [[], [], []]
            self._eventTriggers[eventType] = triglist
        evtList = triglist[{"before": 0, "during": 1, "after": 2}[phase]]
        evtList.append((f, args, kw))
        return (phase, eventType, (f, args, kw))

    def removeSystemEventTrigger(self, triggerID):
        """See twisted.internet.interfaces.IReactorCore.removeSystemEventTrigger.
        """
        phase, eventType, item = triggerID
        self._eventTriggers[eventType][{"before": 0,
                                        "during": 1,
                                        "after":  2}[phase]
                                       ].remove(item)


    # IReactorTime

    def callLater(self, seconds, f, *args, **kw):
        """See twisted.internet.interfaces.IReactorTime.callLater.
        """
        assert callable(f)
        tple = DelayedCall(time() + seconds, f, args, kw, self._pendingTimedCalls.remove, self._resetCallLater)
        insort(self._pendingTimedCalls, tple)
        return tple

    def _resetCallLater(self, tple):
        assert tple in self._pendingTimedCalls
        self._pendingTimedCalls.remove(tple)
        insort(self._pendingTimedCalls, tple)
        return tple

    def cancelCallLater(self, callID):
        """See twisted.internet.interfaces.IReactorTime.cancelCallLater.
        """
        warnings.warn("reactor.cancelCallLater(callID) is deprecated - use callID.cancel() instead")
        callID.cancel()

    def getDelayedCalls(self):
        return tuple(self._pendingTimedCalls)
    
    def timeout(self):
        if self._pendingTimedCalls:
            t = self._pendingTimedCalls[0].time - time()
            if t < 0:
                t = 0
            mt = _nmin(t, self._delayeds.timeout())
            return mt
        else:
            return self._delayeds.timeout()

    def runUntilCurrent(self):
        """Run all pending timed calls.
        """
        if self.threadCallQueue:
            for i in range(len(self.threadCallQueue)):
                callable, args, kw = self.threadCallQueue.pop(0)
                try:
                    apply(callable, args, kw)
                except:
                    log.deferr()
        now = time()
        while self._pendingTimedCalls and (self._pendingTimedCalls[0].time <= now):
            call = self._pendingTimedCalls.pop(0)
            try:
                call.called = 1
                apply(call.func, call.args, call.kw)
            except:
                log.deferr()
        self._delayeds.runUntilCurrent()


    # IReactorThreads

    threadpool = None

    def _initThreadPool(self):
        from twisted.python import threadpool, threadable
        threadable.init(1)
        self.threadpool = threadpool.ThreadPool(0, 10)
        self.threadpool.start()
        self.addSystemEventTrigger('during', 'shutdown', self.threadpool.stop)

    def callInThread(self, callable, *args, **kwargs):
        if not self.threadpool:
            self._initThreadPool()
        apply(self.threadpool.dispatch, (log.logOwner.owner(), callable) + args, kwargs)

    def suggestThreadPoolSize(self, size):
        if not self.threadpool:
            self._initThreadPool()
        theThreadPool = self.threadpool
        oldSize = theThreadPool.max
        theThreadPool.max = size
        if oldSize > size:
            from twisted.python import threadpool
            for i in range(oldSize - size):
                theThreadPool.q.put(threadpool.WorkerStop)
            else:
                theThreadPool._startSomeWorkers()


    # backwards compatibility

    def clientUNIX(self, address, protocol, timeout=30):
        """Deprecated - use connectUNIX instead.
        """
        import warnings
        warnings.warn("clientUNIX is deprecated - use connectUNIX instead.",
                      category=DeprecationWarning, stacklevel=2)
        f = BCFactory(protocol)
        self.connectUNIX(address, f, timeout)


    def clientTCP(self, host, port, protocol, timeout=30):
        """Deprecated - use connectTCP instead.
        """
        import warnings
        warnings.warn("clientTCP is deprecated - use connectTCP instead.",
                      category=DeprecationWarning, stacklevel=2)
        f = BCFactory(protocol)
        self.connectTCP(host, port, f, timeout)
        return f

    def clientSSL(self, host, port, protocol, contextFactory, timeout=30):
        """Deprecated - use connectSSL instead.
        """
        import warnings
        warnings.warn("clientSSL is deprecated - use connectSSL instead.",
                      category=DeprecationWarning, stacklevel=2)
        f = BCFactory(protocol)
        self.connectSSL(host, port, f, contextFactory, timeout)




from protocol import ClientFactory

class BCFactory(ClientFactory):
    """Factory for backwards compatability with old clientXXX APIs."""

    def __init__(self, protocol):
        self.protocol = protocol
        self.connector = None

    def startedConnecting(self, connector):
        self.connector = connector

    def loseConnection(self):
        if self.connector:
            self.connector.stopConnecting()
        elif self.protocol:
            self.protocol.transport.loseConnection()

    def buildProtocol(self, addr):
        self.connector = None
        return self.protocol

    def clientConnectionFailed(self, connector, reason):
        self.connector = None
        self.protocol.connectionFailed()
        self.protocol = None


__all__ = ["ReactorBase"]
