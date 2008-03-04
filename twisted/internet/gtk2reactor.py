# -*- test-case-name: twisted.internet.test.test_gtk2reactor -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
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

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import sys
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
from twisted.internet.interfaces import IReactorFDSet
from twisted.internet import main, posixbase, error, selectreactor

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

    @ivar _reads: A dictionary mapping L{FileDescriptor} instances to gtk
        INPUT_READ watch handles.

    @ivar _writes: A dictionary mapping L{FileDescriptor} instances to gtk
        INTPUT_WRITE watch handles.

    @ivar _simtag: A gtk timeout handle for the next L{simulate} call.
    """
    implements(IReactorFDSet)

    def __init__(self, useGtk=True):
        self.context = gobject.main_context_default()
        self.loop = gobject.MainLoop()
        self._simtag = None
        self._reads = {}
        self._writes = {}
        posixbase.PosixReactorBase.__init__(self)
        # pre 2.3.91 the glib iteration and mainloop functions didn't release
        # global interpreter lock, thus breaking thread and signal support.
        if (hasattr(gobject, "pygtk_version") and gobject.pygtk_version >= (2, 3, 91)
            and not useGtk):
            self.__pending = self.context.pending
            self.__iteration = self.context.iteration
            self.__crash = self.loop.quit
            self.__run = self.loop.run
        else:
            import gtk
            self.__pending = gtk.events_pending
            self.__iteration = gtk.main_iteration
            self.__crash = _our_mainquit
            self.__run = gtk.main

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
        if reader not in self._reads:
            self._reads[reader] = self.input_add(reader, INFLAGS, self.callback)

    def addWriter(self, writer):
        if writer not in self._writes:
            self._writes[writer] = self.input_add(writer, OUTFLAGS, self.callback)


    def getReaders(self):
        return self._reads.keys()


    def getWriters(self):
        return self._writes.keys()


    def removeAll(self):
        return self._removeAll(self._reads, self._writes)

    def removeReader(self, reader):
        if reader in self._reads:
            gobject.source_remove(self._reads[reader])
            del self._reads[reader]

    def removeWriter(self, writer):
        if writer in self._writes:
            gobject.source_remove(self._writes[writer])
            del self._writes[writer]

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
        if self.running:
            self.__run()

    def _doReadOrWrite(self, source, condition, faildict={
        error.ConnectionDone: failure.Failure(error.ConnectionDone()),
        error.ConnectionLost: failure.Failure(error.ConnectionLost()),
        }):
        why = None
        didRead = None
        if condition & POLL_DISCONNECTED and \
               not (condition & gobject.IO_IN):
            why = main.CONNECTION_LOST
        else:
            try:
                if condition & gobject.IO_IN:
                    why = source.doRead()
                    didRead = source.doRead
                if not why and condition & gobject.IO_OUT:
                    # if doRead caused connectionLost, don't call doWrite
                    # if doRead is doWrite, don't call it again.
                    if not source.disconnected and source.doWrite != didRead:
                        why = source.doWrite()
                        didRead = source.doWrite # if failed it was in write
            except:
                why = sys.exc_info()[1]
                log.msg('Error In %s' % source)
                log.deferr()

        if why:
            self._disconnectSelectable(source, why, didRead == source.doRead)

    def callback(self, source, condition):
        log.callWithLogger(source, self._doReadOrWrite, source, condition)
        self.simulate() # fire Twisted timers
        return 1 # 1=don't auto-remove the source

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
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
    """Reactor that works on Windows.

    input_add is not supported on GTK+ for Win32, apparently.
    """

    def crash(self):
        selectreactor.SelectReactor.crash(self)
        import gtk
        # mainquit is deprecated in newer versions
        if hasattr(gtk, 'main_quit'):
            gtk.main_quit()
        else:
            gtk.mainquit()

    def run(self, installSignalHandlers=1):
        import gtk
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.simulate()
        # mainloop is deprecated in newer versions
        if hasattr(gtk, 'main'):
            gtk.main()
        else:
            gtk.mainloop()

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
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
    """Configure the twisted mainloop to be run inside the gtk mainloop.

    @param useGtk: should glib rather than GTK+ event loop be
    used (this will be slightly faster but does not support GUI).
    """
    reactor = Gtk2Reactor(useGtk)
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor

def portableInstall(useGtk=True):
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = PortableGtkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor

if runtime.platform.getType() != 'posix':
    install = portableInstall


__all__ = ['install']
