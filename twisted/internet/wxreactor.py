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
This module provides support for Twisted to interact with the wxPython.

In order to use this support, simply do the following::

    |  from twisted.internet import wxreactor
    |  wxreactor.install()

Then, when your root wxApp has been created::

    | from twisted.internet import reactor
    | reactor.registerWxApp(yourApp)
    | reactor.run()

Then use twisted.internet APIs as usual. Stop the event loop using
reactor.stop().

IMPORTANT: tests will fail when run under this reactor. This is expected
and does not reflect on the reactor's ability to run real applications,
I think. Talk to me if you have questions. -- itamar


API Stability: unstable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

from twisted.python.runtime import seconds
from twisted.python import log
from twisted.internet import default

from wxPython.wx import wxTimer, wxApp


class ReactorTimer(wxTimer):
    """Run reactor event loop every millisecond."""

    # The wx docs promise no better than 1ms and no worse than 1s (!) 
    # Experiments have shown that Linux, gets better than 50K timer 
    # calls per second --  however, Windows only gets around 100 
    # timer calls per second. Caveat coder.
    def __init__(self, reactor): 
        wxTimer.__init__(self) 
        self.reactor = reactor
        self.Start(1) 
 
    def Notify(self): 
        """Called every timer interval"""
        self.reactor.simulate()


class DummyApp(wxApp):
    
    def OnInit(self):
        return True


class WxReactor(default.SelectReactor):
    """wxPython reactor.

    wx drives the event loop, and calls Twisted every millisecond, and
    Twisted then iterates until a ms has passed.
    """

    def registerWxApp(self, wxapp):
        """Register wxApp instance with the reactor."""
        self.wxapp = wxapp
    
    def crash(self):
        default.SelectReactor.crash(self)
        self.timer.Stop()
        del self.timer
        self.wxapp.ExitMainLoop()

    def run(self, installSignalHandlers=1):
        if not hasattr(self, "wxapp"):
            log.msg("registerWxApp() was not called on reactor, this is probably an error.")
            self.wxapp = DummyApp(0)
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.timer = ReactorTimer(self)
        self.wxapp.MainLoop()
    
    def simulate(self):
        """Run simulation loops and reschedule callbacks.
        """
        if self.running:
            t = 0.01
            start = seconds()
            while t > 0:
                self.iterate(t)
                t = 0.01 - (seconds() - start)


def install():
    """Configure the twisted mainloop to be run inside the wxPython mainloop.
    """
    reactor = WxReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor


__all__ = ['install']
