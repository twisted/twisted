
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

    |  from twisted.internet import ingtkernet
    |  ingtkernet.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.
"""

__all__ = ['install']

# System Imports
import gtk
import sys

# Twisted Imports
from twisted.python import log, threadable

# Sibling Imports
import main, default

reads = default.reads
writes = default.writes
hasReader = reads.has_key
hasWriter = writes.has_key

# the next callback
_simtag = None


class GtkReactor(default.PosixReactorBase):
    """GTK+ event loop reactor.
    """

    def addReader(self, reader):
        if not hasReader(reader):
            reads[reader] = gtk.input_add(reader, gtk.GDK.INPUT_READ, self.callback)
        self.simulate()

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

    def doIteration(self, delay=0.0):
        if delay != 0:
            log.msg("Error, gtk doIteration() only supports delay of 0")
        gtk.mainiteration()
    
    def crash(self):
        gtk.mainquit()

    def run(self):
        self.startRunning()
        self.simulate()
        gtk.mainloop()

    def callback(self, source, condition):
        methods = []
        cbNames = []

        if condition & gtk.GDK.INPUT_READ:
            methods.append(getattr(source, 'doRead'))
            cbNames.append('doRead')

        if (condition & gtk.GDK.INPUT_WRITE):
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
                why = main.CONNECTION_LOST
                log.msg('Error In %s.%s' %(source,cbName))
                log.deferr()
            if why:
                try:
                    source.connectionLost()
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


def install():
    # Replace 'main' methods with my own
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = GtkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor
