# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
This module provides support for Twisted to interact with the glib/gtk2 mainloop.

In order to use this support, simply do the following::

    |  from twisted.internet import gtk2reactor
    |  gtk2reactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.

The reactor will only use gtk+ if it's already been imported, otherwise
it will run directly on the gobject event loop.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

__all__ = ['install']

# System Imports
import sys
import gobject
try:
    if not hasattr(sys, 'frozen'):
        # Don't want to check this for py2exe
        import pygtk
        pygtk.require('2.0')
except ImportError, AttributeError:
    pass # maybe we're using pygtk before this hack existed.

# Twisted Imports
from twisted.python import log, threadable, runtime, failure
from twisted.internet.interfaces import IReactorFDSet, IDelayedCall
from twisted.python.runtime import seconds

# Sibling Imports
from twisted.internet import main, default, error, base

reads = default.reads
writes = default.writes
hasReader = reads.has_key
hasWriter = writes.has_key

# the next callback
_simtag = None
POLL_DISCONNECTED = gobject.IO_HUP | gobject.IO_ERR | gobject.IO_NVAL

# glib's iochannel sources won't tell us about any events that we haven't
# asked for, even if those events aren't sensible inputs to the poll()
# call.
INFLAGS = gobject.IO_IN | POLL_DISCONNECTED
OUTFLAGS = gobject.IO_OUT | POLL_DISCONNECTED


class DelayedCall:

    __implements__ = IDelayedCall,

    cancelled = False
    called = False
    
    def __init__(self, time, f, args, kw):
        self.start = seconds()
        self.time = time
        self.f = f
        self.args = args
        self.kw = kw
        self.id = gobject.timeout_add(int(time * 1000), self._runScheduled, f, args, kw)

    def _runScheduled(self, f, args, kw):
        try:
            f(*args, **kw)
        except:
            log.err()
        self.called = True
        return False

    def getTime(self):
        return self.start + self.time

    def cancel(self):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        self.cancelled = True
        gobject.source_remove(self.id)
    
    def delay(self, secondsLater):
        self.cancel()
        self.__init__((self.getTime() + secondsLater) - seconds(), self.f, self.args, self.kw)
        self.cancelled = False
        self.called = False
        
    def reset(self, secondsFromNow):
        self.cancel()
        self.__init__(secondsFromNow, self.f, self.args, self.kw)
        self.cancelled = False
        self.called = False
    
    def active(self):
        return not (self.cancelled or self.called)


class Gtk2Reactor(default.PosixReactorBase):
    """GTK+-2 event loop reactor.
    """

    __implements__ = (default.PosixReactorBase.__implements__, IReactorFDSet)

    def __init__(self):
        default.PosixReactorBase.__init__(self)
        self.context = gobject.main_context_default()
        self.loop = gobject.MainLoop()
    
    # The input_add function in pygtk1 checks for objects with a
    # 'fileno' method and, if present, uses the result of that method
    # as the input source. The pygtk2 input_add does not do this. The
    # function below replicates the pygtk1 functionality.

    # In addition, pygtk maps gtk.input_add to _gobject.io_add_watch, and
    # g_io_add_watch() takes different condition bitfields than
    # gtk_input_add(). We use g_io_add_watch() here in case pygtk fixes this
    # bug.
    def input_add(self, source, condition, callback):
        if hasattr(source, 'fileno'):
            # handle python objects
            def wrapper(source, condition, real_s=source, real_cb=callback):
                return real_cb(real_s, condition)
            return gobject.io_add_watch(source.fileno(), condition, wrapper)
        else:
            return gobject.io_add_watch(source, condition, callback)

    def addReader(self, reader):
        if not hasReader(reader):
            reads[reader] = self.input_add(reader, INFLAGS, self.callback)

    def addWriter(self, writer):
        if not hasWriter(writer):
            writes[writer] = self.input_add(writer, OUTFLAGS, self.callback)

    def removeAll(self):
        v = reads.keys()
        for reader in v:
            self.removeReader(reader)
        return v

    def removeReader(self, reader):
        if hasReader(reader):
            gobject.source_remove(reads[reader])
            del reads[reader]

    def removeWriter(self, writer):
        if hasWriter(writer):
            gobject.source_remove(writes[writer])
            del writes[writer]

    def _runScheduled(self, f, args, kw):
        try:
           f(*args, **kw)
        except:
            log.err()
        return False

    def callFromThread(self, f, *args, **kw):
        gobject.timeout_add(0, self._runScheduled, f, args, kw)
        self.wakeUp()
    
    def callLater(self, _seconds, _f, *args, **kw):
        return DelayedCall(_seconds, _f, args, kw)

    def iterate(self, timeout=0):
        if timeout == 0:
            if self.context.pending():
                import gtk
                self.context.iteration(0)
            return
        gobject.timeout_add(int(1000 * timeout), lambda: False)
        self.context.iteration(1)
    
    def crash(self):
        self.__crash()

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        if sys.modules.has_key("gtk"):
            import gtk
            self.__crash = gtk.main_quit
            #gtk.main()
        else:
            self.__crash = self.loop.quit
            self.loop.run()
    
    def _doReadOrWrite(self, source, condition, faildict={
        error.ConnectionDone: failure.Failure(error.ConnectionDone()),
        error.ConnectionLost: failure.Failure(error.ConnectionLost())  }):
        why = None
        if condition & POLL_DISCONNECTED and \
               not (condition & gobject.IO_IN):
            why = main.CONNECTION_LOST
        else:
            try:
                didRead = None
                if condition & gobject.IO_IN:
                    why = source.doRead()
                    didRead = source.doRead
                if not why and condition & gobject.IO_OUT:
                    # if doRead caused connectionLost, don't call doWrite
                    # if doRead is doWrite, don't call it again.
                    if not source.disconnected and source.doWrite != didRead:
                        why = source.doWrite()
            except:
                why = sys.exc_info()[1]
                log.msg('Error In %s' % source)
                log.deferr()

        if why:
            self.removeReader(source)
            self.removeWriter(source)
            f = faildict.get(why.__class__)
            if f:
                source.connectionLost(f)
            else:
                source.connectionLost(failure.Failure(why))

    def callback(self, source, condition):
        log.callWithLogger(source, self._doReadOrWrite, source, condition)
        return 1 # 1=don't auto-remove the source


class PortableGtkReactor(default.SelectReactor):
    """Reactor that works on Windows.

    input_add is not supported on GTK+ for Win32, apparently.
    """

    def crash(self):
        import gtk
        gtk.mainquit()

    def run(self, installSignalHandlers=1):
        import gtk
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.simulate()
        gtk.mainloop()

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
        """
        global _simtag
        if _simtag is not None:
            gobject.source_remove(_simtag)
        self.iterate()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        # grumble
        _simtag = gobject.timeout_add(int(timeout * 1010), self.simulate)


def install():
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = Gtk2Reactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor

def portableInstall():
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = PortableGtkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor

if runtime.platform.getType() != 'posix':
    install = portableInstall
