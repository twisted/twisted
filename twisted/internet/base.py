

"""Very basic functionality for a Reactor implementation.
"""

import socket # needed only for sync-dns

from time import time
from bisect import insort

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL
from twisted.internet.interfaces import IReactorProcess
from twisted.internet import main
from twisted.python import threadable, log
from twisted.python.defer import Deferred, DeferredList

class ReactorBase:
    """Default base class for Reactors.
    """

    __implements__ = IReactorCore, IReactorTime
    installed = 0

    def __init__(self):
        self._eventTriggers = {}
        self._pendingTimedCalls = []
        self._delayeds = main._delayeds
        self.addSystemEventTrigger('during', 'shutdown', self.crash)
        self.addSystemEventTrigger('during', 'shutdown', self.disconnectAll)

    # override in subclasses

    wakerInstalled = 0
    _lock = None

    def initThreads(self):
        import thread
        import Queue
        self.installWaker()
        self.threadCallQueue = Queue.Queue()

    threadCallQueue = None

    def installWaker(self):
        raise NotImplementedError()

    def callFromThread(self, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.callFromThread.
        """
        # apply(task.schedule, (callable,)+ args, kw)
        #print self, 'calling "from thread"', callable, args, kw
        if threadable.isInIOThread():
            #print self, ' not in a thread'
            apply(self.callLater, (0, callable)+ args, kw)
            #print self, ' did it'
        else:
            # print self, ' in a thread'
            self.threadCallQueue.put((callable, args, kw))
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
        from twisted.python.defer import Deferred
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
        # TODO: fire 'shutdown' event.
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
                reader.connectionLost()
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
            DeferredList(defrList).addBoth(self._cbContinueSystemEvent, eventType).arm()
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

    def addSystemEventTrigger(self, phase, eventType, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.addSystemEventTrigger.
        """
        if self._eventTriggers.has_key(eventType):
            triglist = self._eventTriggers[eventType]
        else:
            triglist = [[], [], []]
            self._eventTriggers[eventType] = triglist
        evtList = triglist[{"before": 0, "during": 1, "after": 2}[phase]]
        evtList.append((callable, args, kw))
        return (phase, eventType, (callable, args, kw))

    def removeSystemEventTrigger(self, triggerID):
        """See twisted.internet.interfaces.IReactorCore.removeSystemEventTrigger.
        """
        phase, eventType, item = triggerID
        self._eventTriggers[eventType][{"before": 0,
                                        "during": 1,
                                        "after":  2}[phase]
                                       ].remove(item)


    # IReactorTime

    def callLater(self, seconds, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorTime.callLater.
        """
        tple = (time() + seconds, callable, args, kw)
        insort(self._pendingTimedCalls, tple)
        # print self, 'calling later', self._pendingTimedCalls, tple
        return tple

    def cancelCallLater(self, callID):
        """See twisted.internet.interfaces.IReactorTime.cancelCallLater.
        """
        # print self, 'cancelling call'
        self._pendingTimedCalls.remove(callID)

    def timeout(self):
        if self._pendingTimedCalls:
            t = self._pendingTimedCalls[0][0] - time()
            if t < 0:
                return 0
            else:
                return min(t, self._delayeds.timeout())
        else:
            return self._delayeds.timeout()

    def runUntilCurrent(self):
        """Run all pending timed calls.
        """
        # print self, 'running until current', self.threadCallQueue, self._pendingTimedCalls
        if self.threadCallQueue:
            from Queue import Empty
            while 1:
                try:
                    callable, args, kw = self.threadCallQueue.get(0)
                except Empty:
                    break
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


