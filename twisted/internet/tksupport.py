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

"""This module integrates Tkinter with twisted.internet's mainloop.

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}

To use, do::

    | tksupport.install(rootWidget)

and then run your reactor as usual - do *not* call Tk's mainloop(),
use Twisted's regular mechanism for running the event loop.
"""

# system imports
import Tkinter

# twisted imports
from twisted.python import log


def _guiUpdate(reactor, widget, delay):
    try:
        widget.update() # do all pending GUI events
    except Tkinter.TclError:
        log.deferr()
        return
    reactor.callLater(delay, _guiUpdate, reactor, widget, delay)


def install(widget, ms=10, doShutdown=1, reactor=None):
    """Install a Tkinter.Tk() object into the reactor."""
    if reactor is None:
        from twisted.internet import reactor
    if doShutdown:
        # close twisted on tkinter root destruction
        widget.protocol("WM_DELETE_WINDOW", reactor.stop)
    _guiUpdate(reactor, widget, ms/1000.0)


__all__ = ["install"]
