
"""
This module provides support for Twisted to interact with the glib mainloop.
This is like gtk2, but slightly faster and does not require a working
$DISPLAY. However, you cannot run GUIs under this reactor: for that you must
use the gtk2reactor instead.

In order to use this support, simply do the following::

    |  from twisted.internet import glib2reactor
    |  glib2reactor.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.

When installing the reactor, you can choose whether to use the glib
event loop or the GTK+ event loop which is based on it but adds GUI
integration.

Maintainer: Itamar Shtull-Trauring
"""

from twisted.internet import gtk2reactor



class Glib2Reactor(gtk2reactor.Gtk2Reactor):
    """
    The reactor using the glib mainloop.
    """

    def __init__(self):
        """
        Override init to set the C{useGtk} flag.
        """
        gtk2reactor.Gtk2Reactor.__init__(self, useGtk=False)



def install():
    """
    Configure the twisted mainloop to be run inside the glib mainloop.
    """
    reactor = Glib2Reactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    
__all__ = ['install']

