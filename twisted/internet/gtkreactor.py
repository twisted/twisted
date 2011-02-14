# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module provides support for Twisted to interact with the PyGTK mainloop.

In order to use this support, simply do the following::

    |  from twisted.internet import gtkreactor
    |  gtkreactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.
"""

import sys

# System Imports
try:
    import pygtk
    pygtk.require('1.2')
except ImportError, AttributeError:
    pass # maybe we're using pygtk before this hack existed.
import gtk

from zope.interface import implements

# Twisted Imports
from twisted.python import log, runtime, deprecate, versions
from twisted.internet.interfaces import IReactorFDSet

# Sibling Imports
from twisted.internet import posixbase, selectreactor


deprecatedSince = versions.Version("Twisted", 10, 1, 0)
deprecationMessage = ("All new applications should be written with gtk 2.x, "
                      "which is supported by twisted.internet.gtk2reactor.")


class GtkReactor(posixbase.PosixReactorBase):
    """
    GTK+ event loop reactor.

    @ivar _reads: A dictionary mapping L{FileDescriptor} instances to gtk INPUT_READ
        watch handles.

    @ivar _writes: A dictionary mapping L{FileDescriptor} instances to gtk
        INTPUT_WRITE watch handles.

    @ivar _simtag: A gtk timeout handle for the next L{simulate} call.
    """
    implements(IReactorFDSet)

    deprecate.deprecatedModuleAttribute(deprecatedSince, deprecationMessage,
                                        __name__, "GtkReactor")

    def __init__(self):
        """
        Initialize the file descriptor tracking dictionaries and the base
        class.
        """
        self._simtag = None
        self._reads = {}
        self._writes = {}
        posixbase.PosixReactorBase.__init__(self)


    def addReader(self, reader):
        if reader not in self._reads:
            self._reads[reader] = gtk.input_add(reader, gtk.GDK.INPUT_READ, self.callback)

    def addWriter(self, writer):
        if writer not in self._writes:
            self._writes[writer] = gtk.input_add(writer, gtk.GDK.INPUT_WRITE, self.callback)


    def getReaders(self):
        return self._reads.keys()


    def getWriters(self):
        return self._writes.keys()


    def removeAll(self):
        return self._removeAll(self._reads, self._writes)


    def removeReader(self, reader):
        if reader in self._reads:
            gtk.input_remove(self._reads[reader])
            del self._reads[reader]

    def removeWriter(self, writer):
        if writer in self._writes:
            gtk.input_remove(self._writes[writer])
            del self._writes[writer]

    doIterationTimer = None

    def doIterationTimeout(self, *args):
        self.doIterationTimer = None
        return 0 # auto-remove
    def doIteration(self, delay):
        # flush some pending events, return if there was something to do
        # don't use the usual "while gtk.events_pending(): mainiteration()"
        # idiom because lots of IO (in particular test_tcp's
        # ProperlyCloseFilesTestCase) can keep us from ever exiting.
        log.msg(channel='system', event='iteration', reactor=self)
        if gtk.events_pending():
            gtk.mainiteration(0)
            return
        # nothing to do, must delay
        if delay == 0:
            return # shouldn't delay, so just return
        self.doIterationTimer = gtk.timeout_add(int(delay * 1000),
                                                self.doIterationTimeout)
        # This will either wake up from IO or from a timeout.
        gtk.mainiteration(1) # block
        # note: with the .simulate timer below, delays > 0.1 will always be
        # woken up by the .simulate timer
        if self.doIterationTimer:
            # if woken by IO, need to cancel the timer
            gtk.timeout_remove(self.doIterationTimer)
            self.doIterationTimer = None

    def crash(self):
        posixbase.PosixReactorBase.crash(self)
        gtk.mainquit()

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        gtk.timeout_add(0, self.simulate)
        gtk.mainloop()

    def _readAndWrite(self, source, condition):
        # note: gtk-1.2's gtk_input_add presents an API in terms of gdk
        # constants like INPUT_READ and INPUT_WRITE. Internally, it will add
        # POLL_HUP and POLL_ERR to the poll() events, but if they happen it
        # will turn them back into INPUT_READ and INPUT_WRITE. gdkevents.c
        # maps IN/HUP/ERR to INPUT_READ, and OUT/ERR to INPUT_WRITE. This
        # means there is no immediate way to detect a disconnected socket.

        # The g_io_add_watch() API is more suited to this task. I don't think
        # pygtk exposes it, though.
        why = None
        didRead = None
        try:
            if condition & gtk.GDK.INPUT_READ:
                why = source.doRead()
                didRead = source.doRead
            if not why and condition & gtk.GDK.INPUT_WRITE:
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
        log.callWithLogger(source, self._readAndWrite, source, condition)
        self.simulate() # fire Twisted timers
        return 1 # 1=don't auto-remove the source

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
        """
        if self._simtag is not None:
            gtk.timeout_remove(self._simtag)
        self.runUntilCurrent()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        # Quoth someone other than me, "grumble", yet I know not why. Try to be
        # more specific in your complaints, guys. -exarkun
        self._simtag = gtk.timeout_add(int(timeout * 1010), self.simulate)



class PortableGtkReactor(selectreactor.SelectReactor):
    """Reactor that works on Windows.

    input_add is not supported on GTK+ for Win32, apparently.

    @ivar _simtag: A gtk timeout handle for the next L{simulate} call.
    """
    _simtag = None

    deprecate.deprecatedModuleAttribute(deprecatedSince, deprecationMessage,
                                        __name__, "PortableGtkReactor")

    def crash(self):
        selectreactor.SelectReactor.crash(self)
        gtk.mainquit()

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.simulate()
        gtk.mainloop()

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
        """
        if self._simtag is not None:
            gtk.timeout_remove(self._simtag)
        self.iterate()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1

        # See comment for identical line in GtkReactor.simulate.
        self._simtag = gtk.timeout_add((timeout * 1010), self.simulate)



def install():
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = GtkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor

deprecate.deprecatedModuleAttribute(deprecatedSince, deprecationMessage,
                                    __name__, "install")


def portableInstall():
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = PortableGtkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor

deprecate.deprecatedModuleAttribute(deprecatedSince, deprecationMessage,
                                    __name__, "portableInstall")


if runtime.platform.getType() != 'posix':
    install = portableInstall

__all__ = ['install']
