# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module provides support for Twisted to interact with the glib
mainloop via GObject Introspection.

In order to use this support, simply do the following::

    from twisted.internet import gireactor
    gireactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.
"""

import sys

if 'gobject' in sys.modules:
    raise ImportError(
        "Introspected and static glib/gtk bindings must not be mixed; can't "
        "import gireactor since pygtk2 module is already imported.")

from gi.repository import GLib
GLib.threads_init()

from twisted.internet import _glibbase
from twisted.python import runtime

# We need to override sys.modules with these to prevent imports.
# This is required, as importing these can result in SEGFAULTs.
sys.modules['glib'] = None
sys.modules['gobject'] = None
sys.modules['gio'] = None
sys.modules['gtk'] = None



class GIReactor(_glibbase.GlibReactorBase):
    """
    GObject-introspection event loop reactor.
    """
    _POLL_DISCONNECTED = (GLib.IOCondition.HUP | GLib.IOCondition.ERR |
                          GLib.IOCondition.NVAL)
    _POLL_IN = GLib.IOCondition.IN
    _POLL_OUT = GLib.IOCondition.OUT

    # glib's iochannel sources won't tell us about any events that we haven't
    # asked for, even if those events aren't sensible inputs to the poll()
    # call.
    INFLAGS = _POLL_IN | _POLL_DISCONNECTED
    OUTFLAGS = _POLL_OUT | _POLL_DISCONNECTED

    def __init__(self, useGtk=False):
        _gtk = None
        if useGtk is True:
            from gi.repository import Gtk as _gtk

        _glibbase.GlibReactorBase.__init__(self, GLib, _gtk, useGtk=useGtk)



class PortableGIReactor(_glibbase.PortableGlibReactorBase):
    """
    Portable GObject Introspection event loop reactor.
    """
    def __init__(self, useGtk=False):
        _gtk = None
        if useGtk is True:
            from gi.repository import Gtk as _gtk

        _glibbase.PortableGlibReactorBase.__init__(self, GLib, _gtk,
                                                   useGtk=useGtk)


def install(useGtk=False):
    """
    Configure the twisted mainloop to be run inside the glib mainloop.

    @param useGtk: should GTK+ rather than glib event loop be
        used (this will be slightly slower but does support GUI).
    """
    if runtime.platform.getType() == 'posix':
        reactor = GIReactor(useGtk=useGtk)
    else:
        reactor = PortableGIReactor(useGtk=useGtk)

    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor


__all__ = ['install']
