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

"""
This module provides support for Twisted to interact with the PyGTK2 mainloop.

In order to use this support, simply do the following::

    |  from twisted.internet import gtk2reactor
    |  gtk2reactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

__all__ = ['install']

# System Imports
import sys, time
try:
    if not hasattr(sys, 'frozen'):
        # Don't want to check this for py2exe
        import pygtk
        pygtk.require('2.0')
except ImportError, AttributeError:
    pass # maybe we're using pygtk before this hack existed.
import gtk

# Twisted Imports
from twisted.python import log, threadable, runtime, failure
from twisted.internet.interfaces import IReactorFDSet

# Sibling Imports
from twisted.internet import main, default, error

reads = default.reads
writes = default.writes
hasReader = reads.has_key
hasWriter = writes.has_key

# the next callback
_simtag = None
POLL_DISCONNECTED = gtk._gobject.IO_HUP | gtk._gobject.IO_ERR | \
                    gtk._gobject.IO_NVAL

# gtk's iochannel sources won't tell us about any events that we haven't
# asked for, even if those events aren't sensible inputs to the poll()
# call.
INFLAGS = gtk._gobject.IO_IN | POLL_DISCONNECTED
OUTFLAGS = gtk._gobject.IO_OUT | POLL_DISCONNECTED


class Gtk2Reactor(default.PosixReactorBase):
    """GTK+-2 event loop reactor.
    """

    __implements__ = (default.PosixReactorBase.__implements__, IReactorFDSet)

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
            return gtk._gobject.io_add_watch(source.fileno(), condition,
                                             wrapper)
        else:
            return gtk._gobject.io_add_watch(source, condition, callback)

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
            gtk.input_remove(reads[reader])
            del reads[reader]

    def removeWriter(self, writer):
        if hasWriter(writer):
            gtk.input_remove(writes[writer])
            del writes[writer]

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
            gtk.main_iteration(0)
            return
        # nothing to do, must delay
        if delay == 0:
            return # shouldn't delay, so just return
        self.doIterationTimer = gtk.timeout_add(int(delay * 1000),
                                                self.doIterationTimeout)
        # This will either wake up from IO or from a timeout.
        gtk.main_iteration(1) # block
        # note: with the .simulate timer below, delays > 0.1 will always be
        # woken up by the .simulate timer
        if self.doIterationTimer:
            # if woken by IO, need to cancel the timer
            gtk.timeout_remove(self.doIterationTimer)
            self.doIterationTimer = None

    def crash(self):
        gtk.main_quit()

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.simulate()
        gtk.main()

    def _doReadOrWrite(self, source, condition, faildict={
        error.ConnectionDone: failure.Failure(error.ConnectionDone()),
        error.ConnectionLost: failure.Failure(error.ConnectionLost())  }):
        why = None
        if condition & POLL_DISCONNECTED and \
               not (condition & gtk._gobject.IO_IN):
            why = main.CONNECTION_LOST
        else:
            try:
                didRead = None
                if condition & gtk._gobject.IO_IN:
                    why = source.doRead()
                    didRead = source.doRead
                if not why and condition & gtk._gobject.IO_OUT:
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
        self.simulate() # fire Twisted timers
        return 1 # 1=don't auto-remove the source

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
        """
        global _simtag
        if _simtag is not None:
            gtk.timeout_remove(_simtag)
        self.runUntilCurrent()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        # grumble
        _simtag = gtk.timeout_add(int(timeout * 1010), self.simulate)


class PortableGtkReactor(default.SelectReactor):
    """Reactor that works on Windows.

    input_add is not supported on GTK+ for Win32, apparently.
    """

    def crash(self):
        gtk.mainquit()

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.simulate()
        gtk.mainloop()

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
        """
        global _simtag
        if _simtag is not None:
            gtk.timeout_remove(_simtag)
        self.iterate()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        # grumble
        _simtag = gtk.timeout_add(int(timeout * 1010), self.simulate)


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
