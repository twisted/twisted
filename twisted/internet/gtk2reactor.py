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
try:
    import pygtk
    pygtk.require('2.0')
except ImportError, AttributeError:
    pass # maybe we're using pygtk before this hack existed.
import gtk
import sys

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


class Gtk2Reactor(default.PosixReactorBase):
    """GTK+-2 event loop reactor.
    """

    __implements__ = (default.PosixReactorBase.__implements__, IReactorFDSet)

    # The input_add function in pygtk1 checks for objects with a
    # 'fileno' method and, if present, uses the result of that method
    # as the input source. The pygtk2 input_add does not do this. The
    # function below replicates the pygtk1 functionality.
    def input_add(self, source, condition, callback):
	if hasattr(source, 'fileno'):
            # handle python objects
            def wrapper(source, condition, real_s=source, real_cb=callback):
                real_cb(real_s, condition)
            return gtk.input_add(source.fileno(), condition, wrapper)
        else:
            return gtk.input_add(source, condition, callback)

    def addReader(self, reader):
        if not hasReader(reader):
            reads[reader] = self.input_add(reader,
                                           gtk.gdk.INPUT_READ, self.callback)
        self.simulate()

    def addWriter(self, writer):
        if not hasWriter(writer):
            writes[writer] = self.input_add(writer,
                                            gtk.gdk.INPUT_WRITE, self.callback)

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

    def doIteration(self, delay=0.0):
        if delay != 0:
            log.msg("Error, gtk doIteration() only supports delay of 0")
        gtk.main_iteration()

    def crash(self):
        gtk.main_quit()

    def run(self):
        self.startRunning()
        self.simulate()
        gtk.main()

    def callback(self, source, condition):
        methods = []
        cbNames = []

        if condition & gtk.gdk.INPUT_READ:
            methods.append(getattr(source, 'doRead'))
            cbNames.append('doRead')

        if (condition & gtk.gdk.INPUT_WRITE):
            method = getattr(source, 'doWrite')
            # if doRead is doWrite, don't add it again.
            if not (method in methods):
                methods.append(method)
                cbNames.append('doWrite')

        for method, cbName in map(None, methods, cbNames):
            why = None
            try:
                method = getattr(source, cbName)
                why = method()
            except:
                why = sys.exc_value
                log.msg('Error In %s.%s' %(source,cbName))
                log.deferr()
            if why:
                try:
                    source.connectionLost(failure.Failure(why))
                except:
                    log.deferr()
                self.removeReader(source)
                self.removeWriter(source)
                break
            elif source.disconnected:
                # If source disconnected, don't call the rest of the methods.
                break
        self.simulate()

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

    def run(self):
        self.startRunning()
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
