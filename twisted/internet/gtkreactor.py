
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
This module provides support for Twisted to interact with the PyGTK mainloop.

In order to use this support, simply do the following::

    |  from twisted.internet import gtkreactor
    |  gtkreactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

__all__ = ['install']

# System Imports
try:
    import pygtk
    pygtk.require('1.2')
except ImportError, AttributeError:
    pass # maybe we're using pygtk before this hack existed.
import gtk
import sys, time

# Twisted Imports
from twisted.python import log, threadable, runtime, failure
from twisted.internet.interfaces import IReactorFDSet

# Sibling Imports
from twisted.internet import main, default

reads = default.reads
writes = default.writes
hasReader = reads.has_key
hasWriter = writes.has_key

# the next callback
_simtag = None


class GtkReactor(default.PosixReactorBase):
    """GTK+ event loop reactor.
    """

    __implements__ = (default.PosixReactorBase.__implements__, IReactorFDSet)

    def addReader(self, reader):
        if not hasReader(reader):
            reads[reader] = gtk.input_add(reader, gtk.GDK.INPUT_READ, self.callback)

    def addWriter(self, writer):
        if not hasWriter(writer):
            writes[writer] = gtk.input_add(writer, gtk.GDK.INPUT_WRITE, self.callback)

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
            gtk.mainiteration(0)
            return
        # nothing to do, must delay
        if delay == 0:
            return # shouldn't delay, so just return
        self.doIterationTimer = gtk.timeout_add(delay * 1000,
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
        gtk.mainquit()

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.simulate()
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
        try:
            didRead = None
            if condition & gtk.GDK.INPUT_READ:
                why = source.doRead()
                didRead = source.doRead
            if not why and condition & gtk.GDK.INPUT_WRITE:
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
            source.connectionLost(failure.Failure(why))

    def callback(self, source, condition):
        log.callWithLogger(source, self._readAndWrite, source, condition)
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
        _simtag = gtk.timeout_add(timeout * 1010, self.simulate) # grumble


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
        _simtag = gtk.timeout_add(timeout * 1010, self.simulate) # grumble


def install():
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = GtkReactor()
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
