# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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
