
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
This module provides support for Twisted to interact with the Tkinter mainloop.

In order to use this support, simply do the following::

    |  from twisted.internet import tkreactor
    |  tkreactor.install()
    
If a root widget is instantiated before tkreactor.install() is invoked, it
will be assigned to twisted.internet.reactor.root, otherwise Tkinter.Tk()
will be called and assigned to twisted.internet.reactor.root

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.

API Stability: stable

Maintainer: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

__all__ = ['install']

# System Imports
import Tkinter
import sys

# Twisted Imports
from twisted.python import log, threadable, runtime, failure
from twisted.internet.interfaces import IReactorFDSet

# Sibling Imports
import main, default

reads = default.reads
writes = default.writes
hasReader = reads.has_key
hasWriter = writes.has_key

class TkReactor(default.SelectReactor):
    """Tkinter event loop reactor."""

    # The root Tk widget
    root = None

    _simtag = None

    def crash(self):
        self.root.quit()

    def run(self):
        self.startRunning()
        self.simulate()
        self.root.mainloop()

    def simulate(self):
        """Run simulation loops and reschedule callbacks.
        """
        if self._simtag is not None:
            self.root.after_cancel(self._simtag)
        self.iterate()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        self._simtag = self.root.after(int(timeout * 1010), self.simulate) # grumble


def install():
    """Configure the twisted mainloop to be run inside the Tk mainloop.
    """
    reactor = TkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    
    reactor.root = Tkinter._default_root
    if not reactor.root:
        reactor.root = Tkinter.Tk()

    return reactor
