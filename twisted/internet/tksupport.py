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

Likewise, to stop your program you will need to stop Twisted's
event loop. For example, if you want closing your root widget to
stop Twisted::

    | root.protocol('WM_DELETE_WINDOW', reactor.stop)

"""

# system imports
import Tkinter, tkSimpleDialog, tkMessageBox

# twisted imports
from twisted.python import log


def _guiUpdate(reactor, widget, delay):
    try:
        widget.update() # do all pending GUI events
    except Tkinter.TclError:
        log.deferr()
        return
    reactor.callLater(delay, _guiUpdate, reactor, widget, delay)


def install(widget, ms=10, reactor=None):
    """Install a Tkinter.Tk() object into the reactor."""
    if reactor is None:
        from twisted.internet import reactor
    _guiUpdate(reactor, widget, ms/1000.0)
    
    installTkFunctions()


def installTkFunctions():
    import twisted.python.util
    twisted.python.util.getPassword = getPassword


def getPassword(prompt = '', confirm = 0):
    while 1:
        try1 = tkSimpleDialog.askstring('Password Dialog', prompt, show='*')
        if not confirm:
            return try1
        try2 = tkSimpleDialog.askstring('Password Dialog', 'Confirm Password', show='*')
        if try1 == try2:
            return try1
        else:
            tkMessageBox.showerror('Password Mismatch', 'Passwords did not match, starting over')

__all__ = ["install"]
