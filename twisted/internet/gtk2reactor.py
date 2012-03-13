# -*- test-case-name: twisted.internet.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
This module provides support for Twisted to interact with the glib/gtk2
mainloop.

In order to use this support, simply do the following::

    from twisted.internet import gtk2reactor
    gtk2reactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.
"""

# System Imports
import sys

# Twisted Imports
from twisted.internet import _glibbase
from twisted.python import runtime

_glibbase.ensureNotImported(
    ["gi"],
    "Introspected and static glib/gtk bindings must not be mixed; can't "
    "import gtk2reactor since gi module is already imported.",
    preventImports=["gi"])

try:
    if not hasattr(sys, 'frozen'):
        # Don't want to check this for py2exe
        import pygtk
        pygtk.require('2.0')
except (ImportError, AttributeError):
    pass # maybe we're using pygtk before this hack existed.

import gobject
if hasattr(gobject, "threads_init"):
    # recent versions of python-gtk expose this. python-gtk=2.4.1
    # (wrapping glib-2.4.7) does. python-gtk=2.0.0 (wrapping
    # glib-2.2.3) does not.
    gobject.threads_init()



class Gtk2Reactor(_glibbase.GlibReactorBase):
    """
    PyGTK+ 2 event loop reactor.
    """
    _POLL_DISCONNECTED = gobject.IO_HUP | gobject.IO_ERR | gobject.IO_NVAL
    _POLL_IN = gobject.IO_IN
    _POLL_OUT = gobject.IO_OUT

    # glib's iochannel sources won't tell us about any events that we haven't
    # asked for, even if those events aren't sensible inputs to the poll()
    # call.
    INFLAGS = _POLL_IN | _POLL_DISCONNECTED
    OUTFLAGS = _POLL_OUT | _POLL_DISCONNECTED

    def __init__(self, useGtk=True):
        _gtk = None
        if useGtk is True:
            import gtk as _gtk

        _glibbase.GlibReactorBase.__init__(self, gobject, _gtk, useGtk=useGtk)



class PortableGtkReactor(_glibbase.PortableGlibReactorBase):
    """
    Reactor that works on Windows.

    Sockets aren't supported by GTK+'s input_add on Win32.
    """
    def __init__(self, useGtk=True):
        _gtk = None
        if useGtk is True:
            import gtk as _gtk

        _glibbase.PortableGlibReactorBase.__init__(self, gobject, _gtk,
                                                   useGtk=useGtk)


def install(useGtk=True):
    """
    Configure the twisted mainloop to be run inside the gtk mainloop.

    @param useGtk: should glib rather than GTK+ event loop be
        used (this will be slightly faster but does not support GUI).
    """
    reactor = Gtk2Reactor(useGtk)
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor


def portableInstall(useGtk=True):
    """
    Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = PortableGtkReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor


if runtime.platform.getType() != 'posix':
    install = portableInstall


__all__ = ['install']
