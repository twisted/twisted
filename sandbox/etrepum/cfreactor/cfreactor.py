# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
This module provides support for Twisted to interact with CoreFoundation
CFRunLoops.  This includes Cocoa's NSRunLoop.

In order to use this support, simply do the following::

    |  from twisted.internet import cfreactor
    |  cfreactor.install()

Then use the twisted.internet APIs as usual.  The other methods here are not
intended to be called directly under normal use.  However, install can take
a runLoop kwarg, and run will take a withRunLoop arg if you need to explicitly
pass a CFRunLoop for some reason.  Otherwise it will make a pretty good guess
as to which runLoop you want (the current NSRunLoop if PyObjC is imported,
otherwise the current CFRunLoop.  Either way, if one doesn't exist, it will
be created).

API Stability: stable

Maintainer: U{Bob Ippolito<mailto:bob@redivi.com>}
"""

__all__ = ['install']

import sys
from Foundation import *
from cfsupport import *

from twisted.python import log, threadable, failure
from twisted.internet import main, default, error
from weakref import WeakKeyDictionary

# cache two extremely common "failures" without traceback info
_faildict = {
    error.ConnectionDone: failure.Failure(error.ConnectionDone()),
    error.ConnectionLost: failure.Failure(error.ConnectionLost()),
}

class ConnectionLostReplacement(object):
    def __init__(self, delegate, obj):
        self.delegate = delegate
        self.obj = obj
        self.connectionLost = obj.connectionLost

    def __call__(self, *args, **kwargs):
        obj = self.obj
        reactor = self.delegate.reactor
        reactor.removeReader(obj)
        reactor.removeWriter(obj)
        obj.connectionLost = self.connectionLost
        try:
            obj.connectionLost(*args, **kwargs)
        finally:
            self.delegate.removeSelectable(obj)

def setCFSocketFlags(cf, reading, writing):
    mask = kCFSocketConnectCallBack | kCFSocketAcceptCallBack
    offmask = 0
    automask = kCFSocketAutomaticallyReenableAcceptCallBack
    if reading:
        mask |= kCFSocketReadCallBack
        automask |= kCFSocketAutomaticallyReenableReadCallBack
    else:
        offmask |= kCFSocketReadCallBack
    if writing:
        mask |= kCFSocketWriteCallBack
        automask |= kCFSocketAutomaticallyReenableWriteCallBack
    else:
        offmask |= kCFSocketWriteCallBack
    CFSocketDisableCallBacks(cf, offmask)
    CFSocketEnableCallBacks(cf, mask)
    CFSocketSetSocketFlags(cf, automask)

class CFReactorSocketDelegate(CFSocketDelegate):
    def init(self):
        self = super(CFReactorSocketDelegate, self).init()
        self.sockets = {}
        self.selectables = {}
        return self
        
    def addSelectable(self, reactor, obj):
        if obj in self.selectables:
            return cf
        obj.connectionLost = ConnectionLostReplacement(self, obj)
        cf = reactor.manager.createSocketWithNativeHandle_flags_(
            self.fd,
            (
                kCFSocketConnectCallBack |
                kCFSocketReadCallBack |
                kCFSocketWriteCallBack
            ),
        )
        source = CFSocketCreateRunLoopSource(kCFAllocatorDefault, cf, 10000)
        # reading, writing, wouldRead, wouldWrite
        flags = (False, False, False, False)
        self.sockets[cf] = [obj, reactor, flags]
        self.selectables[obj] = cf
        setCFSocketFlags(cf, False, False)
        CFRunLoopAddSource(reactor.getCFRunLoop(), source, kCFRunLoopDefaultMode)
        CFRelease(source)
        return cf
 
    def removeSelectable(self, obj):
        cf = self.selectables.pop(obj)
        del self.sockets[cf]
        CFSocketInvalidate(cf)
        CFRelease(cf)
    
    def readCallBackWithSocket_(self, cf):
        lst = self.sockets[cf]
        self._doRead(cf, lst)

    def writeCallBackWithSocket_(self, cf):
        lst = self.sockets[cf]
        self._doWrite(cf, lst)

    def startReading(self, obj):
        cf = self.addSelectable(obj)
        lst = self.sockets[cf]
        reactor = lst[1]
        reading, writing, wouldRead, wouldWrite = lst[2]
        lst[2] = (True, writing, False, wouldWrite)
        if not reading:
            setCFSocketFlags(cf, True, writing)
        if wouldRead:
            if not reactor.running:
                self.reactor.callLater(0, self._finishReadOrWrite, obj.doRead)
            else:
                self._finishReadOrWrite(obj.doRead, cf, lst)
        return self

    def startWriting(self, obj):
        cf = self.addSelectable(obj)
        lst = self.sockets[cf]
        reactor = lst[1]
        reading, writing, wouldRead, wouldWrite = lst[2]
        lst[2] = (reading, True, wouldRead, True)
        if not writing:
            setCFSocketFlags(cf, reading, True)
        if wouldWrite:
            if not reactor.running:
                self.reactor.callLater(0, self._finishReadOrWrite, obj.doWrite)
            else:
                self._finishReadOrWrite(obj.doWrite, cf, lst)
        return self

    def stopReading(self, obj):
        cf = self.addSelectable(obj)
        lst = self.sockets[cf]
        reactor = lst[1]
        reading, writing, wouldRead, wouldWrite = lst[2]
        lst[2] = (False, writing, False, wouldWrite)
        if reading:
            setCFSocketFlags(cf, False, writing)
        return self

    def stopWriting(self, obj):
        cf = self.addSelectable(obj)
        lst = self.sockets[cf]
        reactor = lst[1]
        reading, writing, wouldRead, wouldWrite = lst[2]
        lst[2] = (reading, False, wouldRead, False)
        if writing:
            setCFSocketFlags(cf, reading, False)
        return self
    
    def _finishReadOrWrite(self, fn, cf, lst, faildict=_faildict):
        try:
            why = fn(cf, lst)
        except:
            why = sys.exc_info()[1]
            log.err()
        if why:
            try:
                f = faildict.get(why.__class__) or failure.Failure(why)
                lst[0].connectionLost.connectionLost(f)
            except:
                log.err()
        if reactor.running:
            reactor.simulate()

    def _doRead(self, cf, lst):
        reading, writing, wouldRead, wouldWrite = lst[2]
        if not reading:
            lst[2] = False, writing, True, wouldWrite
            reactor = lst[1]
            if reactor.running:
                reactor.simulate()
            return
        self._finishReadOrWrite(obj.doRead, cf, lst)

    def _doWrite(self, cf, lst)
        reading, writing, wouldRead, wouldWrite = lst[2]
        if not writing:
            lst[2] = reading, False, wouldRead, True
            reactor = lst[1]
            if reactor.running:
                reactor.simulate()
            return
        self._finishReadOrWrite(obj.doWrite, cf, lst)

class CFReactor(default.PosixReactorBase):
    # how long to poll if we're don't care about signals
    longIntervalOfTime = 60.0 

    # how long we should poll if we do care about signals
    shortIntervalOfTime = 1.0

    # don't set this
    pollInterval = longIntervalOfTime

    def __init__(self, runLoop=None):
        self.manager = CFSocketManager.alloc().init()
        self.delegate = CFReactorSocketDelegate.alloc().initWithReactor_(self)
        self.manager.setDelegate_(self.delegate)
        self.readers = {}
        self.writers = {}
        self.running = 0
        self.crashing = False
        self._doRunUntilCurrent = True
        self.timer = None
        self.runLoop = None
        self.inheritedRunLoop = runLoop is not None 
        if self.inheritedRunLoop:
            self.getRunLoop(runLoop)
        default.PosixReactorBase.__init__(self)

    def installWaker(self):
        # I don't know why, but the waker causes 100% CPU
        # so for now we don't install one, ever.
        return
    
    def getRunLoop(self, runLoop=None):
        if self.runLoop is None:
            # If Foundation is loaded, assume they want the current
            # NSRunLoop, not the base CFRunLoop.
            # If None or an NSRunLoop instance is given, then we assume
            # the user has caused it to begin running.  In reality, 
            # NSApplication probably started it for them.
            #
            # If this is a wrong guess, the user can make the runloop go
            # on their own after reactor.run().  It's a pretty good guess,
            # though.
            if 'Foundation' in sys.modules:
                from Foundation import NSRunLoop
                nsRunLoop = runLoop or NSRunLoop.currentRunLoop()
                if isinstance(nsRunLoop, NSRunLoop):
                    runLoop = nsRunLoop.getCFRunLoop()
                    self.inheritedRunLoop = True
            self.runLoop = cf.PyCFRunLoop(runLoop)
        return self.runLoop
    
    def addReader(self, reader):
        self.readers[reader] = SelectableSocketWrapper.socketWrapperForReactorAndObject(self, reader).startReading()

    def addWriter(self, writer):
        self.writers[writer] = SelectableSocketWrapper.socketWrapperForReactorAndObject(self, writer).startWriting()

    def removeReader(self, reader):
        wrapped = self.readers.get(reader, None)
        if wrapped is not None:
            del self.readers[reader]
            wrapped.stopReading()

    def removeWriter(self, writer):
        wrapped = self.writers.get(writer, None)
        if wrapped is not None:
            del self.writers[writer]
            wrapped.stopWriting()

    def removeAll(self):
        r = self.readers.keys()
        for s in self.readers.itervalues():
            s.stopReading()
        for s in self.writers.itervalues():
            s.stopWriting()
        self.readers.clear()
        self.writers.clear()
        return r
        
    def run(self, installSignalHandlers=1, withRunLoop=None):
        if self.running:
            raise ValueError, "Reactor already running"
        if installSignalHandlers:
            self.pollInterval = self.shortIntervalOfTime
        runLoop = self.getRunLoop(withRunLoop)
        self._startup()
       
        self.startRunning(installSignalHandlers=installSignalHandlers)

        self.running = True
        if not self.inheritedRunLoop:
            # Inherited runLoops are assumed to be running already,
            # but we created this one so we have to start it.
            runLoop.run()
            self.crashing = False

    def callLater(self, howlong, *args, **kwargs):
        rval = default.PosixReactorBase.callLater(self, howlong, *args, **kwargs)
        if self.timer:
            timeout = self.timeout()
            if timeout is None:
                timeout = howlong
            sleepUntil = cf.now() + min(timeout, howlong)
            if sleepUntil < self.timer.getNextFireDate():
                self.timer.setNextFireDate(sleepUntil)
        else:
            pass
        return rval
        
    def iterate(self, howlong=0.0):
        if self.running:
            raise ValueError, "Can't iterate a running reactor"
        self.runUntilCurrent()
        self.doIteration(howlong)
        
    def doIteration(self, howlong):
        if self.running:
            raise ValueError, "Can't iterate a running reactor"
        howlong = howlong or 0.01
        pi = self.pollInterval
        self.pollInterval = howlong
        self._doRunUntilCurrent = False
        self.run()
        self._doRunUntilCurrent = True
        self.pollInterval = pi

    def simulate(self):
        if self.crashing:
            return
        if not self.running:
            raise ValueError, "You can't simulate a stopped reactor"
        if self._doRunUntilCurrent:
            self.runUntilCurrent()
        if self.crashing:
            return
        if self.timer is None:
            return
        nap = self.timeout()
        if nap is None:
            nap = self.pollInterval
        else:
            nap = min(self.pollInterval, nap)
        if self.running:
            self.timer.setNextFireDate(cf.now() + nap)
        if not self._doRunUntilCurrent:
            self.crash()
        
    def _startup(self):
        if self.running:
            raise ValueError, "Can't bootstrap a running reactor"
        self.timer = cf.PyCFRunLoopTimer(cf.now(), self.pollInterval, self.simulate)
        self.runLoop.addTimer(self.timer)

    def cleanup(self):
        pass

    def sigInt(self, *args):
        self.callLater(0.0, self.stop)

    def crash(self):
        if not self.running:
            raise ValueError, "Can't crash a stopped reactor"
        self.running = False
        self.crashing = True
        if self.timer is not None:
            self.runLoop.removeTimer(self.timer)
            self.timer = None
        if not self.inheritedRunLoop:
            self.runLoop.stop()

    def stop(self):
        if not self.running:
            raise ValueError, "Can't stop a stopped reactor"
        default.PosixReactorBase.stop(self)

def install(runLoop=None):
    """Configure the twisted mainloop to be run inside CFRunLoop.
    """
    reactor = CFReactor(runLoop=runLoop)
    reactor.addSystemEventTrigger('after', 'shutdown', reactor.cleanup)
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor
