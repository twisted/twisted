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

Maintainer: U{Bob Ippolito<mailto:bob@redivi.com>}
"""

__all__ = ['install']

import sys

# hints for py2app
import Carbon.CF
import traceback

import cfsupport as cf

from zope.interface import implements

from twisted.python import log, threadable, failure
from twisted.internet.interfaces import IReactorFDSet
from twisted.internet import posixbase, error
from weakref import WeakKeyDictionary
from Foundation import NSRunLoop
from AppKit import NSApp

# cache two extremely common "failures" without traceback info
_faildict = {
    error.ConnectionDone: failure.Failure(error.ConnectionDone()),
    error.ConnectionLost: failure.Failure(error.ConnectionLost()),
}

class SelectableSocketWrapper(object):
    _objCache = WeakKeyDictionary()

    cf = None
    def socketWrapperForReactorAndObject(klass, reactor, obj):
        _objCache = klass._objCache
        if obj in _objCache:
            return _objCache[obj]
        v = _objCache[obj] = klass(reactor, obj)
        return v
    socketWrapperForReactorAndObject = classmethod(socketWrapperForReactorAndObject)
        
    def __init__(self, reactor, obj):
        if self.cf:
            raise ValueError, "This socket wrapper is already initialized"
        self.reactor = reactor
        self.obj = obj
        obj._orig_ssw_connectionLost = obj.connectionLost
        obj.connectionLost = self.objConnectionLost
        self.fd = obj.fileno()
        self.writing = False
        self.reading = False
        self.wouldRead = False
        self.wouldWrite = False
        self.cf = cf.PyCFSocket(obj.fileno(), self.doRead, self.doWrite, self.doConnect)
        self.cf.stopWriting()
        reactor.getRunLoop().addSocket(self.cf)
       
    def __repr__(self):
        return 'SSW(fd=%r r=%r w=%r x=%08x o=%08x)' % (self.fd, int(self.reading), int(self.writing), id(self), id(self.obj))

    def objConnectionLost(self, *args, **kwargs):
        obj = self.obj
        self.reactor.removeReader(obj)
        self.reactor.removeWriter(obj)
        obj.connectionLost = obj._orig_ssw_connectionLost
        obj.connectionLost(*args, **kwargs)
        try:
            del self._objCache[obj]
        except:
            pass
        self.obj = None
        self.cf = None

    def doConnect(self, why):
        pass

    def startReading(self):
        self.cf.startReading()
        self.reading = True
        if self.wouldRead:
            if not self.reactor.running:
                self.reactor.callLater(0, self.doRead)
            else:
                self.doRead()
            self.wouldRead = False
        return self

    def stopReading(self):
        self.cf.stopReading()
        self.reading = False
        self.wouldRead = False
        return self

    def startWriting(self):
        self.cf.startWriting()
        self.writing = True
        if self.wouldWrite:
            if not self.reactor.running:
                self.reactor.callLater(0, self.doWrite)
            else:
                self.doWrite()
            self.wouldWrite = False
        return self

    def stopWriting(self):
        self.cf.stopWriting()
        self.writing = False
        self.wouldWrite = False
    
    def _finishReadOrWrite(self, fn, faildict=_faildict):
        try:
            why = fn()
        except:
            why = sys.exc_info()[1]
            log.err()
        if why:
            try:
                f = faildict.get(why.__class__) or failure.Failure(why)
                self.objConnectionLost(f)
            except:
                log.err()
        if self.reactor.running:
            self.reactor.simulate()

    def doRead(self):
        obj = self.obj
        if not obj:
            return
        if not self.reading:
            self.wouldRead = True
            if self.reactor.running:
                self.reactor.simulate()
            return
        self._finishReadOrWrite(obj.doRead)

    def doWrite(self):
        obj = self.obj
        if not obj:
            return
        if not self.writing:
            self.wouldWrite = True
            if self.reactor.running:
                self.reactor.simulate()
            return
        self._finishReadOrWrite(obj.doWrite)
 
    def __hash__(self):
        return hash(self.fd)

class CFReactor(posixbase.PosixReactorBase):
    implements(IReactorFDSet)
    # how long to poll if we're don't care about signals
    longIntervalOfTime = 60.0 

    # how long we should poll if we do care about signals
    shortIntervalOfTime = 1.0

    # don't set this
    pollInterval = longIntervalOfTime

    def __init__(self, runLoop=None):
        self.readers = {}
        self.writers = {}
        self.running = 0
        self.crashing = False
        self._doRunUntilCurrent = True
        self.timer = None
        self.runLoop = None
        self.nsRunLoop = None
        self.didStartRunLoop = False
        if runLoop is not None:
            self.getRunLoop(runLoop)
        posixbase.PosixReactorBase.__init__(self)

    def getRunLoop(self, runLoop=None):
        if self.runLoop is None:
            self.nsRunLoop = runLoop or NSRunLoop.currentRunLoop()
            self.runLoop = cf.PyCFRunLoop(self.nsRunLoop.getCFRunLoop())
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


    def getReaders(self):
        return self.readers.keys()


    def getWriters(self):
        return self.writers.keys()


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
        if NSApp() is None and self.nsRunLoop.currentMode() is None:
            # Most of the time the NSRunLoop will have already started,
            # but in this case it wasn't.
            runLoop.run()
            self.crashing = False
            self.didStartRunLoop = True

    def callLater(self, howlong, *args, **kwargs):
        rval = posixbase.PosixReactorBase.callLater(self, howlong, *args, **kwargs)
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
        posixbase.PosixReactorBase.crash(self)
        self.crashing = True
        if self.timer is not None:
            self.runLoop.removeTimer(self.timer)
            self.timer = None
        if self.didStartRunLoop:
            self.runLoop.stop()

    def stop(self):
        if not self.running:
            raise ValueError, "Can't stop a stopped reactor"
        posixbase.PosixReactorBase.stop(self)

def install(runLoop=None):
    """Configure the twisted mainloop to be run inside CFRunLoop.
    """
    reactor = CFReactor(runLoop=runLoop)
    reactor.addSystemEventTrigger('after', 'shutdown', reactor.cleanup)
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor
