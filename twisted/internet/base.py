# -*- test-case-name: twisted.test.test_internet -*-
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
try:
    import fcntl
except ImportError:
    fcntl = None

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX, IReactorThreads
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL
from twisted.internet.interfaces import IReactorProcess, IReactorPluggableResolver
from twisted.internet.interfaces import IConnector, IDelayedCall
from twisted.internet import main, error, abstract, defer
from twisted.python import threadable, log, failure, reflect
from twisted.internet.defer import Deferred, DeferredList
from twisted.persisted import styles


def _nmin(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)



class DelayedCall(styles.Ephemeral):
    
    __implements__ = IDelayedCall
    
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

    def active(self):
        return not (self.cancelled or self.called)

    def __lt__(self, other):
        # Order reversed for efficiency concerns, see below
        return self.time >= other.time

    def __str__(self):
        try:
            func = self.func.func_name
            try:
                func = self.func.im_class.__name__ + '.' + func
            except:
                func = self.func
                if hasattr(func, 'func_code'):
                    func = func.func_code # func_code's repr sometimes has more useful info
        except:
            func = reflect.safe_repr(self.func)
        return "<DelayedCall [%ds] called=%s cancelled=%s %s%s>" % (self.time - time(), self.called, self.cancelled, func,
                                                                    reflect.safe_repr(self.args))


class ReactorBase:
    """Default base class for Reactors.
    """

    __implements__ = IReactorCore, IReactorTime, IReactorThreads, IReactorPluggableResolver
    installed = 0

    __name__ = "twisted.internet.reactor"

    def __init__(self):
        self._eventTriggers = {}
        self._pendingTimedCalls = []
        self.waker = None
        self.resolver = None
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

    def installResolver(self, resolver):
        self.resolver = resolver

    def callFromThread(self, f, *args, **kw):
        """See twisted.internet.interfaces.IReactorThreads.callFromThread.
        """
        assert callable(f), "%s is not callable" % f
        if threadable.isInIOThread():
            self.callLater(0, f, *args, **kw)
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

    def resolve(self, name, timeout = 10):
        """Return a Deferred that will resolve a hostname.
        """
        if not name:
            # XXX - This is *less than* '::', and will screw up IPv6 servers
            return defer.succeed('0.0.0.0')
        if abstract.isIPAddress(name):
            return defer.succeed(name)
        if self.resolver is None:
            return self._internalResolve(name, timeout)
        return self.resolver.getHostByName(name, timeout)

    def _internalResolve(self, name, timeout):
        try:
            address = socket.gethostbyname(name)
        except socket.error:
            return defer.fail(failure.Failure(error.DNSLookupError("address not found")))
        else:
            return defer.succeed(address)

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
        assert seconds >= 0
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
        # DO NOT DELETE THIS - this is documented in Python in a Nutshell, so we
        # we can't get rid of it for a long time.
        warnings.warn("reactor.cancelCallLater(callID) is deprecated - use callID.cancel() instead")
        callID.cancel()

    def getDelayedCalls(self):
        return tuple(self._pendingTimedCalls)

    def timeout(self):
        if self._pendingTimedCalls:
            t = self._pendingTimedCalls[-1].time - time()
            if t < 0:
                t = 0
            return t
        else:
            return None

    def runUntilCurrent(self):
        """Run all pending timed calls.
        """
        if self.threadCallQueue:
            for i in range(len(self.threadCallQueue)):
                callable, args, kw = self.threadCallQueue.pop(0)
                try:
                    callable(*args, **kw)
                except:
                    log.deferr()
        now = time()
        while self._pendingTimedCalls and (self._pendingTimedCalls[-1].time <= now):
            call = self._pendingTimedCalls.pop()
            try:
                call.called = 1
                call.func(*call.args, **call.kw)
            except:
                log.deferr()


    # IReactorThreads

    threadpool = None

    def _initThreadPool(self):
        from twisted.python import threadpool, threadable
        threadable.init(1)
        self.threadpool = threadpool.ThreadPool(0, 10)
        self.threadpool.start()
        self.addSystemEventTrigger('during', 'shutdown', self.threadpool.stop)

    def callInThread(self, callable, *args, **kwargs):
        """See twisted.internet.interfaces.IReactorThreads.callInThread.
        """
        if not self.threadpool:
            self._initThreadPool()
        self.threadpool.callInThread(callable, *args, **kwargs)

    def suggestThreadPoolSize(self, size):
        """See twisted.internet.interfaces.IReactorThreads.suggestThreadPoolSize.
        """
        if size == 0 and not self.threadpool:
            return
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


class BaseConnector(styles.Ephemeral):
    """Basic implementation of connector.

    State can be: "connecting", "connected", "disconnected"
    """

    __implements__ = IConnector,

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
        if self.timeoutID:
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


class BasePort(abstract.FileDescriptor):
    """Basic implementation of a ListeningPort."""
    
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


__all__ = ["ReactorBase"]
