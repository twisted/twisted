
from bisect import insort
from time import time

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL
from twisted.internet.interfaces import IReactorProcess
from twisted.internet import main, tcp, udp
from twisted.python import log
from twisted.python.defer import DeferredList, Deferred

try:
    from twisted.internet import ssl
    sslEnabled = 1
except:
    sslEnabled = 0

class DefaultSelectReactor:
    __implements__ = IReactorCore, IReactorTime, IReactorUNIX, \
                     IReactorTCP, IReactorUDP, #\
                     # IReactorProcess
    if sslEnabled:
        __implements__ = __implements__ + (IReactorSSL,)

    def __init__(self, installSignalHandlers=1):
        self._installSignalHandlers = installSignalHandlers
        self._eventTriggers = {}
        self._pendingTimedCalls = []

    # Installation.
    def install(self):
        # this stuff should be common to all reactors.
        import twisted.internet
        import sys
        twisted.internet.reactor = self
        sys.modules['twisted.internet.reactor'] = self
        # and this stuff is still yucky workarounds specific to the default case.
        main.addDelayed(self)

    # IReactorCore

    def run(self):
        """See twisted.internet.interfaces.IReactorCore.run.
        """
        main.run(self._installSignalHandlers)


    def stop(self):
        """See twisted.internet.interfaces.IReactorCore.stop.
        """
        # TODO: fire 'shutdown' event.
        main.shutDown()


    def crash(self):
        """See twisted.internet.interfaces.IReactorCore.crash.
        """
        main.stopMainLoop()


    def iterate(self, delay=0):
        """See twisted.internet.interfaces.IReactorCore.iterate.
        """
        main.iterate(delay)


    def callFromThread(self, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.callFromThread.
        """
        apply(task.schedule, (callable,)+ args, kw)


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
            self._continueSystemEvent(eventType)


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

    def callLater(self, delay, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorTime.callLater.
        """
        tple = (time() + seconds, callable, args, kw)
        insort(self._pendingTimedCalls, tple)
        return tple


    def cancelCallLater(self, callID):
        """See twisted.internet.interfaces.IReactorTime.cancelCallLater.
        """
        self._pendingTimedCalls.remove(callID)


    # making myself look like a Delayed

    def timeout(self):
        if self._pendingTimedCalls:
            return max(self._pendingTimedCalls[0][0] - time(), 0)
        else:
            return None

    def runUntilCurrent(self):
        now = time()
        while self._pendingTimedCalls and (self._pendingTimedCalls[0][0] < now):
            seconds, func, args, kw = self._pendingTimedCalls.pop()
            try:
                apply(func, args, kw)
            except:
                log.deferr()


    # IReactorProcess ## XXX TODO!

    # IReactorUDP
    
    def listenUDP(self, port, factory, interface='', maxPacketSize=8192):
        """See twisted.internet.interfaces.IReactorUDP.listenUDP
        """
        return udp.Port(self, port, factory, interface, maxPacketSize)

    # IReactorUNIX
    
    def clientUNIX(address, protocol, timeout=30):
        """See twisted.internet.interfaces.IReactorUNIX.clientUNIX
        """
        return tcp.Client("unix", address, protocol, timeout=timeout)

    def listenUNIX(address, factory, backlog=5):
        """Listen on a UNIX socket.
        """
        return tcp.Port(address, factory, backlog=backlog)


    # IReactorTCP
    
    def listenTCP(self, port, factory, backlog=5, interface=''):
        """See twisted.internet.interfaces.IReactorTCP.listenTCP
        """
        return tcp.Port(port, factory, backlog, interface)

    def clientTCP(self, host, port, protocol, timeout=30):
        """See twisted.internet.interfaces.IReactorTCP.clientTCP
        """
        return tcp.Client(host, port, protocol, timeout)


    # IReactorSSL (sometimes, not implemented)

    def clientSSL(self, host, port, protocol, contextFactory, timeout=30,):
        return ssl.Client(host, port, protocol, contextFactory, timeout)

    def listenSSL(self, port, factory, contextFactory, backlog=5, interface=''):
        return ssl.Port(port, factory, contextFactory, backlog, interface)
