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
"""

import socket # needed only for sync-dns

from time import time
from bisect import insort

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX, IReactorThreads
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL
from twisted.internet.interfaces import IReactorProcess
from twisted.internet import main
from twisted.python import threadable, log
from twisted.internet.defer import Deferred, DeferredList


def _nmin(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)

class ReactorBase:
    """Default base class for Reactors.
    """

    __implements__ = IReactorCore, IReactorTime, IReactorThreads
    installed = 0

    def __init__(self):
        self._eventTriggers = {}
        self._pendingTimedCalls = []
        self._delayeds = main._delayeds
        self.addSystemEventTrigger('during', 'shutdown', self.crash)
        self.addSystemEventTrigger('during', 'shutdown', self.disconnectAll)
        threadable.whenThreaded(self.initThreads)
    
    # override in subclasses

    wakerInstalled = 0
    _lock = None

    def initThreads(self):
        import thread
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
            # this is probably a bug in Jython, but until fixed this code won't work
            # in Jython.
            self.threadCallQueue.append((f, args, kw))
            self.wakeUp()

    def wakeUp(self):
        """Wake up the event loop."""
        if not threadable.isInIOThread():
            self.waker.wakeUp()

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
                deferred.errback("address not found")
            else:
                deferred.callback(address)
        else:
            deferred.errback("type not supportded")
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
            try:
                log.logOwner.own(reader)
                reader.connectionLost(main.CONNECTION_LOST)
                log.logOwner.disown(reader)
            except:
                log.deferr()

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
        tple = (time() + seconds, f, args, kw)
        insort(self._pendingTimedCalls, tple)
        return tple

    def cancelCallLater(self, callID):
        """See twisted.internet.interfaces.IReactorTime.cancelCallLater.
        """
        # print self, 'cancelling call'
        self._pendingTimedCalls.remove(callID)

    def timeout(self):
        if self._pendingTimedCalls:
            # print 'pending timed calls', self._pendingTimedCalls
            t = self._pendingTimedCalls[0][0] - time()
            if t < 0:
                t = 0
            mt = _nmin(t, self._delayeds.timeout())
            # print 'returning mt', mt
            return mt
        else:
            return self._delayeds.timeout()

    def runUntilCurrent(self):
        """Run all pending timed calls.
        """
        # print self, 'running until current', self.threadCallQueue, self._pendingTimedCalls
        if self.threadCallQueue:
            for i in range(len(self.threadCallQueue)):
                callable, args, kw = self.threadCallQueue.pop(0)
                try:
                    # print 'popping the thread queue', self.threadCallQueue.queue
                    apply(callable, args, kw)
                except:
                    log.deferr()
        now = time()
        while self._pendingTimedCalls and (self._pendingTimedCalls[0][0] <= now):
            # print 'calling the callback', now, self._pendingTimedCalls
            seconds, func, args, kw = self._pendingTimedCalls.pop(0)
            try:
                # print self, '_calling_ timed callback', func, args, kw
                apply(func, args, kw)
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
