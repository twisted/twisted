#['PyCFRunLoop', 'PyCFRunLoopTimer', 'PyCFSocket', '__builtins__', '__doc__', '__file__', '__name__', 'now']
import cfsupport as cf
import sys

from twisted.python import log, threadable, failure

from twisted.internet import main, default

from weakref import WeakKeyDictionary

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
            ###log.msg('* %r.__init__(%r, %r) already initialized!' % (self, reactor, obj))
            raise ValueError, "bad bad bad"
        self.reactor = reactor
        self.obj = obj
        obj._orig_ssw_connectionLost = obj.connectionLost
        obj.connectionLost = self.objConnectionLost
        self.fd = obj.fileno()
        self.writing = False
        self.reading = False
        self.wouldRead = False
        self.wouldWrite = False
        ###log.msg('> %r.__init__(%r, %r)' % (self, reactor, obj))
        self.cf = cf.PyCFSocket(obj.fileno(), self.doRead, self.doWrite, self.doConnect)
        reactor.getRunLoop().addSocket(self.cf)
        ###log.msg('< %r.__init__(%r, %r)' % (self, reactor, obj))
       
    def __repr__(self):
        return 'SSW(fd=%r r=%r w=%r x=%08x o=%08x)' % (self.fd, int(self.reading), int(self.writing), id(self), id(self.obj))

    def objConnectionLost(self, *args, **kwargs):
        obj = self.obj
        ###log.msg('> %r.objConnectionLost(*%r, **%r)' % (self, args, kwargs))
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
        ###log.msg('< %r.objConnectionLost(*%r, **%r)' % (self, args, kwargs))

    def doConnect(self, why):
        ###log.msg("* %r.doConnect(%r)" % (self, why))
        pass

    def startReading(self):
        ###log.msg("> %r.startReading()" % (self,))
        self.cf.startReading()
        self.reading = True
        if self.wouldRead:
            ###log.msg('reading because I would have')
            if not self.reactor.running:
                self.reactor.callLater(0, self.doRead)
            else:
                self.doRead()
            self.wouldRead = False
        ###log.msg("< %r.startReading()" % (self,))
        return self

    def stopReading(self):
        ###log.msg("> %r.stopReading()" % (self,))
        self.cf.stopReading()
        self.reading = False
        self.wouldRead = False
        ###log.msg("< %r.stopReading()" % (self,))

    def startWriting(self):
        ###log.msg("> %r.startWriting()" % (self,))
        self.cf.startWriting()
        self.writing = True
        if self.wouldWrite:
            ###log.msg('writing because I would have')
            if not self.reactor.running:
                self.reactor.callLater(0, self.doWrite)
            else:
                self.doWrite()
            self.wouldWrite = False
        ###log.msg("< %r.startWriting()" % (self,))
        return self

    def stopWriting(self):
        ###log.msg("> %r.stopWriting()" % (self,))
        self.cf.stopWriting()
        self.writing = False
        self.wouldWrite = False
        ###log.msg("< %r.stopWriting()" % (self,))
    
    def doRead(self):
        ###log.msg("> %r.doRead()" % (self,))
        reactor = self.reactor
        obj = self.obj
        if not obj:
            ###log.msg("no object?!")
            ###log.msg("< %r.doRead()" % (self,))
            return
        if not self.reading:
            self.wouldRead = True
            ###log.msg("shouldn't be reading")
            if not self.writing:
                ###log.msg("shouldn't be doing anything")
                #reactor.removeReader(obj)
                #reactor.removeWriter(obj)
                #obj.connectionLost(failure.Failure(ValueError("shouldn't be reading")))
                #self.obj = None
                #self.cf = None
                pass
            if reactor.running:
                reactor.simulate()
            else:
                ###log.msg("not simulating, reactor isn't running")
                pass
            ###log.msg("< %r.doRead()" % (self,))
            return
        try:
            ###log.msg('pre doRead')
            why = obj.doRead()
            ###log.msg('post doRead')
        except:
            why = sys.exc_info()[1]
            log.msg('Error in %r.doRead()' % (obj,))
            log.deferr()
        if why:
            try:
                f = failure.Failure(why)
                f.printTraceback()
                ###log.msg('CONNECTION FUCKING LOST ON READ' )
                self.objConnectionLost(f)
            except:
                log.deferr()
        if reactor.running:
            reactor.simulate()
        else:
            ###log.msg("not simulating, reactor isn't running")
            pass
        ###log.msg("< %r.doRead()" % (self,))

    def doWrite(self):
        ###log.msg("> %r.doWrite()" % (self,))
        reactor = self.reactor
        obj = self.obj
        if not obj:
            ###log.msg("no object?!")
            ###log.msg("< %r.doWrite()" % (self,))
            return
        if not self.writing:
            self.wouldWrite = True
            ###log.msg("shouldn't be writing")
            if not self.reading:
                ###log.msg("shouldn't be doing anything")
                #reactor.removeReader(obj)
                #reactor.removeWriter(obj)
                #obj.connectionLost(failure.Failure(ValueError("shouldn't be writing")))
                #self.obj = None
                #self.cf = None
                pass
            if reactor.running:
                reactor.simulate()
            else:
                ###log.msg("not simulating, reactor isn't running")
                pass
            ###log.msg("< %r.doWrite()" % (self,))
            return
        try:
            why = obj.doWrite()
        except:
            why = sys.exc_info()[1]
            log.msg('Error in %r.doWrite()' % (obj,))
            log.deferr()
        if why:
            try:
                f = failure.Failure(why)
                f.printTraceback()
                ###log.msg('CONNECTION FUCKING LOST ON READ' )
                self.objConnectionLost(f)
            except:
                log.deferr()
        if reactor.running:
            reactor.simulate()
        else:
            ###log.msg("not simulating, reactor isn't running")
            pass
        ###log.msg("< %r.doWrite()" % (self,))
 
    def __hash__(self):
        ###log.msg("* %r.__hash__() = %r" % (self, hash(self.fd)))
        return hash(self.fd)

    def __del__(self):
        ###log.msg("* %r.__del__()" % (self,))
        pass
        
readers = {}
writers = {}
    
class CFReactor(default.PosixReactorBase):
    # how long to poll if we're don't care about signals
    longIntervalOfTime = 60.0 

    # how long we should poll if we do care about signals
    shortIntervalOfTime = 1.0

    # don't set this
    pollInterval = longIntervalOfTime

    def __init__(self, app=None):
        self.running = 0
        self.crashing = False
        self._doRunUntilCurrent = True
        self.timer = None
        self.runLoop = None
        self.inheritedRunLoop = False
        default.PosixReactorBase.__init__(self)
        if app is None:
            pass

    def getRunLoop(self, runLoop=None):
        if not self.runLoop:
            ###log.msg("no current run loop")
            ###log.msg("given runloop: %r" % (runLoop,))
            self.runLoop = cf.PyCFRunLoop(runLoop)
            ###log.msg("new runLoop %r.cf = %r" % (self.runLoop, self.runLoop.cf))
        return self.runLoop
    
    def addReader(self, reader):
        ###log.msg('> reactor.addReader(%r)' % (reader,))
        ###log.msg('readers = %r' % (readers,))
        readers[reader] = SelectableSocketWrapper.socketWrapperForReactorAndObject(self, reader).startReading()
        ###log.msg('readers = %r' % (readers,))
        ###log.msg('< reactor.addReader(%r)' % (reader,))

    def addWriter(self, writer):
        ###log.msg('> reactor.addWriter(%r)' % (writer,))
        ###log.msg('writers = %r' % (writers,))
        writers[writer] = SelectableSocketWrapper.socketWrapperForReactorAndObject(self, writer).startWriting()
        ###log.msg('writers = %r' % (writers,))
        ###log.msg('< reactor.addWriter(%r)' % (writer,))

    def removeReader(self, reader):
        ###log.msg('> reactor.removeReader(%r)' % (reader,))
        ###log.msg('readers = %r' % (readers,))
        if reader in readers:
            readers[reader].stopReading()
            del readers[reader]
        ###log.msg('readers = %r' % (readers,))
        ###log.msg('< reactor.removeReader(%r)' % (reader,))

    def removeWriter(self, writer):
        ###log.msg('> reactor.removeWriter(%r)' % (writer,))
        ###log.msg('writers = %r' % (writers,))
        if writer in writers:
            writers[writer].stopWriting()
            del writers[writer]
        ###log.msg('writers = %r' % (writers,))
        ###log.msg('< reactor.removeWriter(%r)' % (writer,))

    def removeAll(self):
        ###log.msg('> reactor.removeAll()')
        r = readers.keys()
        for s in readers.itervalues():
            s.stopReading()
        for s in writers.itervalues():
            s.stopWriting()
        readers.clear()
        writers.clear()
        ###log.msg('< reactor.removeAll()')
        return r
        
    def run(self, installSignalHandlers=1, withRunLoop=None):
        ###log.msg('> reactor.run(installSignalHandlers=%r)' % installSignalHandlers)
        if self.running:
            import pdb
            pdb.set_trace()
        if False and installSignalHandlers:
            self.pollInterval = self.shortIntervalOfTime
        runLoop = self.getRunLoop(withRunLoop)
        self.inheritedRunLoop = withRunLoop is not None
        self._startup()
       
        self.startRunning(installSignalHandlers=installSignalHandlers)

        self.running = True
        if not withRunLoop:
            runLoop.run()
            self.crashing = False
            ###log.msg('< reactor.run(installSignalHandlers=%r)' % installSignalHandlers)

    def callLater(self, howlong, *args, **kwargs):
        ###log.msg('> reactor.callLater(%r, *%r, **%r)' % (howlong, args, kwargs))
        rval = default.PosixReactorBase.callLater(self, howlong, *args, **kwargs)
        if self.timer:
            timeout = self.timeout()
            if timeout is None:
                timeout = howlong
            sleepUntil = cf.now() + min(timeout, howlong)
            if sleepUntil < self.timer.getNextFireDate():
                self.timer.setNextFireDate(sleepUntil)
        else:
            ###log.msg('no timer..')
            pass
        ###log.msg('> reactor.callLater(%r, *%r, **%r)' % (howlong, args, kwargs))
        return rval
        
    def iterate(self, howlong=0.0):
        ###log.msg('> reactor.iterate(%r)' % howlong)
        if self.running:
            import pdb
            pdb.set_trace()
        self.runUntilCurrent()
        self.doIteration(howlong)
        ###log.msg('< reactor.iterate(%r)' % howlong)
        
    def doIteration(self, howlong):
        ###log.msg('> reactor.doIteration(%r)' % howlong)
        if self.running:
            import pdb
            pdb.set_trace()
        if self.running:
            raise ValueError, "Bad monkey!"
        howlong = howlong or 0.01
        pi = self.pollInterval
        self.pollInterval = howlong
        self._doRunUntilCurrent = False
        self.run()
        self._doRunUntilCurrent = True
        self.pollInterval = pi
        ###log.msg('< reactor.doIteration(%r)' % howlong)

    def simulate(self):
        ###log.msg('> reactor.simulate()')
        if self.crashing:
            ###log.msg('socket callback after crash')
            ###log.msg('< reactor.simulate()')
            return
        if not self.running:
            import pdb
            pdb.set_trace()
        if self._doRunUntilCurrent:
            self.runUntilCurrent()
        if self.crashing:
            ###log.msg("Crashing early, bad user!")
            ###log.msg('< reactor.simulate()')
            return
        if self.timer is None:
            ###log.msg("simulate:: NO TIMER")
            return
        nap = self.timeout()
        ###log.msg("  given timeout is %r" % (nap,))
        if nap is None:
            nap = self.pollInterval
        else:
            nap = min(self.pollInterval, nap)
        ###log.msg("  actual timeout is %r" % (nap,))
        if self.running:
            self.timer.setNextFireDate(cf.now() + nap)
        if not self._doRunUntilCurrent:
            self.crash()
        ###log.msg('< reactor.simulate()')
        
    def _startup(self):
        ###log.msg('> reactor._startup()')
        if self.running:
            import pdb
            pdb.set_trace()

        self.timer = cf.PyCFRunLoopTimer(cf.now(), self.pollInterval, self.simulate)
        self.runLoop.addTimer(self.timer)
        ###log.msg('< reactor._startup()')

    def cleanup(self):
        ###log.msg('* reactor.cleanup()')
        pass

    def sigInt(self, *args):
        self.callLater(0.0, self.stop)

    def crash(self):
        ###log.msg('> reactor.crash()')
        if not self.running:
            import pdb
            pdb.set_trace()
        self.running = False
        self.crashing = True
        if self.timer is not None:
            self.runLoop.removeTimer(self.timer)
            self.timer = None
        if not self.inheritedRunLoop:
            self.runLoop.stop()
        ###log.msg('< reactor.crash()')

    def stop(self):
        ###log.msg('> reactor.stop()')
        if not self.running:
            import pdb
            pdb.set_trace()
        default.PosixReactorBase.stop(self)
        ###log.msg('< reactor.stop()')

def install(app=None):
    """Configure the twisted mainloop to be run inside CFRunLoop.
    """
    reactor = CFReactor(app=app)
    reactor.addSystemEventTrigger('after', 'shutdown', reactor.cleanup)
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor
