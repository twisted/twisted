# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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

import time
from twisted.python.runtime import seconds
from twisted.python import log
from twisted.internet import threadedselectreactor

from wxPython.wx import wxApp, wxCallAfter, wxEventLoop, wxFrame, NULL


class DummyApp(wxApp):
    
    def OnInit(self):
        return True


class WxReactor(threadedselectreactor.ThreadedSelectReactor):
    """wxPython reactor.

    wx drives the event loop, and calls Twisted every millisecond, and
    Twisted then iterates until a ms has passed.
    """

    stopping = False
    
    def registerWxApp(self, wxapp):
        """Register wxApp instance with the reactor."""
        self.wxapp = wxapp                    

    def crash(self):
        threadedselectreactor.ThreadedSelectReactor.crash(self)
        if hasattr(self, "wxapp"):
            self.wxapp.ExitMainLoop()

    def _installSignalHandlersAgain(self):
        # stupid wx removes our own signal handlers, so re-add them
        try:
            import signal
            signal.signal(signal.SIGINT, signal.default_int_handler) # make _handleSignals happy
        except ImportError:
            return
        self._handleSignals()

    def stop(self):
        if self.stopping:
            return
        self.stopping = True
        threadedselectreactor.ThreadedSelectReactor.stop(self)
    
    def run(self, installSignalHandlers=1):
        if not hasattr(self, "wxapp"):
            log.msg("registerWxApp() was not called on reactor, this is probably an error.")
            self.registerWxApp(DummyApp(0))
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.interleave(wxCallAfter)
        self.callLater(0, self._installSignalHandlersAgain)
        self.wxapp.MainLoop()
        
        if not self.stopping: # wx exited without reactor.stop(), bah
            self.stop()

        # temporary event loop for dealing with shutdown events:
        ev = wxEventLoop()
        wxEventLoop.SetActive(ev)
        while self.workerThread:
            while ev.Pending():
                ev.Dispatch()
            time.sleep(0.0001) # so we don't use 100% CPU, bleh
            self.wxapp.ProcessIdle()


def install():
    """Configure the twisted mainloop to be run inside the wxPython mainloop.
    """
    reactor = WxReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor


__all__ = ['install']
