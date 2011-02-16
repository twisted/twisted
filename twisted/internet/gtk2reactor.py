# -*- test-case-name: twisted.internet.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
This module provides support for Twisted to interact with the glib/gtk2
mainloop.

In order to use this support, simply do the following::

    |  from twisted.internet import gtk2reactor
    |  gtk2reactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.

When installing the reactor, you can choose whether to use the glib
event loop or the GTK+ event loop which is based on it but adds GUI
integration.
"""

# System Imports
import sys, signal

from zope.interface import implements

try:
    if not hasattr(sys, 'frozen'):
        # Don't want to check this for py2exe
        import pygtk
        pygtk.require('2.0')
except (ImportError, AttributeError):
    pass # maybe we're using pygtk before this hack existed.
import gobject
if hasattr(gobject, "threads_init"):
    # recent versions of python-gtk expose this. python-gtk=2.4.1
    # (wrapping glib-2.4.7) does. python-gtk=2.0.0 (wrapping
    # glib-2.2.3) does not.
    gobject.threads_init()

# Twisted Imports
from twisted.python import log, runtime, failure
from twisted.python.compat import set
from twisted.internet.interfaces import IReactorFDSet
from twisted.internet import main, base, posixbase, error, selectreactor

POLL_DISCONNECTED = gobject.IO_HUP | gobject.IO_ERR | gobject.IO_NVAL

# glib's iochannel sources won't tell us about any events that we haven't
# asked for, even if those events aren't sensible inputs to the poll()
# call.
INFLAGS = gobject.IO_IN | POLL_DISCONNECTED
OUTFLAGS = gobject.IO_OUT | POLL_DISCONNECTED



def _our_mainquit():
    # XXX: gtk.main_quit() (which is used for crash()) raises an exception if
    # gtk.main_level() == 0; however, all the tests freeze if we use this
    # function to stop the reactor.  what gives?  (I believe this may have been
    # a stupid mistake where I forgot to import gtk here... I will remove this
    # comment if the tests pass)
    import gtk
    if gtk.main_level():
        gtk.main_quit()



class Gtk2Reactor(posixbase.PosixReactorBase):
    """
    GTK+-2 event loop reactor.

    @ivar _sources: A dictionary mapping L{FileDescriptor} instances to gtk
        watch handles.

    @ivar _reads: A set of L{FileDescriptor} instances currently monitored for
        reading.

    @ivar _writes: A set of L{FileDescriptor} instances currently monitored for
        writing.

    @ivar _simtag: A gtk timeout handle for the next L{simulate} call.
    """
    implements(IReactorFDSet)

    def __init__(self, useGtk=True):
        self._simtag = None
        self._reads = set()
        self._writes = set()
        self._sources = {}
        posixbase.PosixReactorBase.__init__(self)
        # pre 2.3.91 the glib iteration and mainloop functions didn't release
        # global interpreter lock, thus breaking thread and signal support.
        if getattr(gobject, "pygtk_version", ()) >= (2, 3, 91) and not useGtk:
            self.context = gobject.main_context_default()
            self.__pending = self.context.pending
            self.__iteration = self.context.iteration
            self.loop = gobject.MainLoop()
            self.__crash = self.loop.quit
            self.__run = self.loop.run
        else:
            import gtk
            self.__pending = gtk.events_pending
            self.__iteration = gtk.main_iteration
            self.__crash = _our_mainquit
            self.__run = gtk.main


    if runtime.platformType == 'posix':
        def _handleSignals(self):
            # Let the base class do its thing, but pygtk is probably
            # going to stomp on us so go beyond that and set up some
            # signal handling which pygtk won't mess with.  This would
            # be better done by letting this reactor select a
            # different implementation of installHandler for
            # _SIGCHLDWaker to use.  Then, at least, we could fall
            # back to our extension module.  See #4286.
            from twisted.internet.process import reapAllProcesses as _reapAllProcesses
            base._SignalReactorMixin._handleSignals(self)
            signal.signal(signal.SIGCHLD, lambda *a: self.callFromThread(_reapAllProcesses))
            if getattr(signal, "siginterrupt", None) is not None:
                signal.siginterrupt(signal.SIGCHLD, False)
            # Like the base, reap processes now in case a process
            # exited before the handlers above were installed.
            _reapAllProcesses()

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


    def _add(self, source, primary, other, primaryFlag, otherFlag):
        """
        Add the given L{FileDescriptor} for monitoring either for reading or
        writing. If the file is already monitored for the other operation, we
        delete the previous registration and re-register it for both reading
        and writing.
        """
        if source in primary:
            return
        flags = primaryFlag
        if source in other:
            gobject.source_remove(self._sources[source])
            flags |= otherFlag
        self._sources[source] = self.input_add(source, flags, self.callback)
        primary.add(source)


    def addReader(self, reader):
        """
        Add a L{FileDescriptor} for monitoring of data available to read.
        """
        self._add(reader, self._reads, self._writes, INFLAGS, OUTFLAGS)


    def addWriter(self, writer):
        """
        Add a L{FileDescriptor} for monitoring ability to write data.
        """
        self._add(writer, self._writes, self._reads, OUTFLAGS, INFLAGS)


    def getReaders(self):
        """
        Retrieve the list of current L{FileDescriptor} monitored for reading.
        """
        return list(self._reads)


    def getWriters(self):
        """
        Retrieve the list of current L{FileDescriptor} monitored for writing.
        """
        return list(self._writes)


    def removeAll(self):
        """
        Remove monitoring for all registered L{FileDescriptor}s.
        """
        return self._removeAll(self._reads, self._writes)


    def _remove(self, source, primary, other, flags):
        """
        Remove monitoring the given L{FileDescriptor} for either reading or
        writing. If it's still monitored for the other operation, we
        re-register the L{FileDescriptor} for only that operation.
        """
        if source not in primary:
            return
        gobject.source_remove(self._sources[source])
        primary.remove(source)
        if source in other:
            self._sources[source] = self.input_add(
                source, flags, self.callback)
        else:
            self._sources.pop(source)


    def removeReader(self, reader):
        """
        Stop monitoring the given L{FileDescriptor} for reading.
        """
        self._remove(reader, self._reads, self._writes, OUTFLAGS)


    def removeWriter(self, writer):
        """
        Stop monitoring the given L{FileDescriptor} for writing.
        """
        self._remove(writer, self._writes, self._reads, INFLAGS)


    doIterationTimer = None

    def doIterationTimeout(self, *args):
        self.doIterationTimer = None
        return 0 # auto-remove


    def doIteration(self, delay):
        # flush some pending events, return if there was something to do
        # don't use the usual "while self.context.pending(): self.context.iteration()"
        # idiom because lots of IO (in particular test_tcp's
        # ProperlyCloseFilesTestCase) can keep us from ever exiting.
        log.msg(channel='system', event='iteration', reactor=self)
        if self.__pending():
            self.__iteration(0)
            return
        # nothing to do, must delay
        if delay == 0:
            return # shouldn't delay, so just return
        self.doIterationTimer = gobject.timeout_add(int(delay * 1000),
                                                self.doIterationTimeout)
        # This will either wake up from IO or from a timeout.
        self.__iteration(1) # block
        # note: with the .simulate timer below, delays > 0.1 will always be
        # woken up by the .simulate timer
        if self.doIterationTimer:
            # if woken by IO, need to cancel the timer
            gobject.source_remove(self.doIterationTimer)
            self.doIterationTimer = None


    def crash(self):
        posixbase.PosixReactorBase.crash(self)
        self.__crash()


    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        gobject.timeout_add(0, self.simulate)
        if self._started:
            self.__run()


    def _doReadOrWrite(self, source, condition, faildict={
        error.ConnectionDone: failure.Failure(error.ConnectionDone()),
        error.ConnectionLost: failure.Failure(error.ConnectionLost()),
        }):
        why = None
        inRead = False
        if condition & POLL_DISCONNECTED and not (condition & gobject.IO_IN):
            if source in self._reads:
                why = main.CONNECTION_DONE
                inRead = True
            else:
                why = main.CONNECTION_LOST
        else:
            try:
                if condition & gobject.IO_IN:
                    why = source.doRead()
                    inRead = True
                if not why and condition & gobject.IO_OUT:
                    # if doRead caused connectionLost, don't call doWrite
                    # if doRead is doWrite, don't call it again.
                    if not source.disconnected:
                        why = source.doWrite()
            except:
                why = sys.exc_info()[1]
                log.msg('Error In %s' % source)
                log.deferr()

        if why:
            self._disconnectSelectable(source, why, inRead)


    def callback(self, source, condition):
        log.callWithLogger(source, self._doReadOrWrite, source, condition)
        self.simulate() # fire Twisted timers
        return 1 # 1=don't auto-remove the source


    def simulate(self):
        """
        Run simulation loops and reschedule callbacks.
        """
        if self._simtag is not None:
            gobject.source_remove(self._simtag)
        self.runUntilCurrent()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        # grumble
        self._simtag = gobject.timeout_add(int(timeout * 1010), self.simulate)



class PortableGtkReactor(selectreactor.SelectReactor):
    """
    Reactor that works on Windows.

    Sockets aren't supported by GTK+'s input_add on Win32.
    """
    _simtag = None

    def crash(self):
        selectreactor.SelectReactor.crash(self)
        import gtk
        # mainquit is deprecated in newer versions
        if gtk.main_level():
            if hasattr(gtk, 'main_quit'):
                gtk.main_quit()
            else:
                gtk.mainquit()


    def run(self, installSignalHandlers=1):
        import gtk
        self.startRunning(installSignalHandlers=installSignalHandlers)
        gobject.timeout_add(0, self.simulate)
        # mainloop is deprecated in newer versions
        if hasattr(gtk, 'main'):
            gtk.main()
        else:
            gtk.mainloop()


    def simulate(self):
        """
        Run simulation loops and reschedule callbacks.
        """
        if self._simtag is not None:
            gobject.source_remove(self._simtag)
        self.iterate()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        # grumble
        self._simtag = gobject.timeout_add(int(timeout * 1010), self.simulate)



def install(useGtk=True):
    """
    Configure the twisted mainloop to be run inside the gtk mainloop.

    @param useGtk: should glib rather than GTK+ event loop be
        used (this will be slightly faster but does not support GUI).
    """
    reactor = Gtk2Reactor(useGtk)
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor



def portableInstall(useGtk=True):
    """
    Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = PortableGtkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor



if runtime.platform.getType() != 'posix':
    install = portableInstall



__all__ = ['install']
