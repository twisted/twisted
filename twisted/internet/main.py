
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


# System Imports
import types
import os
import time

import sys
import socket
CONNECTION_LOST = -1
CONNECTION_DONE = -2

theApplication = None

# Twisted Imports

from twisted.python import threadable, log
from twisted.python.runtime import platform
from twisted.persisted import styles
from twisted.python.defer import Deferred, DeferredList


class DummyResolver:
    """
    An implementation of a synchronous resolver, from Python's socket stuff.
    This may be ill-placed.
    """
    def resolve(self, deferred, name, type=1, timeout=10):
        if type != 1:
            deferred.errback("type not supportded")
            return
        try:
            address = socket.gethostbyname(name)
        except socket.error:
            deferred.errback("address not found")
        else:
            deferred.callback(address)


running = None
shuttingDown = None
beforeShutdown = []
duringShutdown = []
afterShutdown = []
resolver = DummyResolver()
interruptCountdown = 5

def shutDown(*ignored):
    """Run all shutdown callbacks (save all running Applications) and exit.

    This is called by various signal handlers which should cause
    the process to exit.  It can also be called directly in order
    to trigger a clean shutdown.
    """
    _getReactor().stop()

def stopMainLoop(*ignored):
    global running
    running = 0
    log.msg("Stopping main loop.")

def _getReactor():
    import twisted.internet
    if not hasattr(twisted.internet, 'reactor'):
        # Work on Jython
        if platform.getType() == 'java':
            import jnternet
            # XXX make jnternet a Reactor
        else:
            import default
            default.install()
    return twisted.internet.reactor


def run(installSignalHandlers=1):
    """Run input/output and dispatched/delayed code.

    This call \"never\" returns.  It is the main loop which runs delayed timers
    (see twisted.python.delay and addDelayed), and the I/O monitor (doSelect).
    """
    global running
    running = 1
    _getReactor().run()


def installReactor(reactor):
    global addReader, addWriter, removeReader, removeWriter
    global iterate, addTimeout, wakeUp
    # this stuff should be common to all reactors.
    import twisted.internet
    import sys
    assert not sys.modules.has_key('twisted.internet.reactor'), \
           "reactor already installed"
    twisted.internet.reactor = reactor
    sys.modules['twisted.internet.reactor'] = reactor

    # install stuff for backwards compatability
    addReader = reactor.addReader
    addWriter = reactor.addWriter
    removeWriter = reactor.removeWriter
    removeReader = reactor.removeReader
    iterate = reactor.iterate
    addTimeout = lambda m, t, f=reactor.callLater: f(t, m)
    wakeUp = reactor.wakeUp



def callWhenRunning(function):
    """Add a function to be called when the system starts running.

    If the system is already running, then the function runs immediately.  If
    the system has not yet started running, the function will be queued to get
    run when the mainloop starts.
    """
    if running:
        function()
    else:
        _getReactor().addSystemEventTrigger('after', 'startup', function)

def callBeforeShutdown(function):
    """Add a function to be called before shutdown begins.

    These functions are tasks to be performed in order to run a
    "clean" shutdown.  This may involve tasks that keep the mainloop
    running, so any function registered in this list may return a
    Deferred, which will delay the actual shutdown until later.
    """
    _getReactor().addSystemEventTrigger('before', 'shutdown', function)

def removeCallBeforeShutdown(function):
    """Remove a function registered with callBeforeShutdown.
    """
    _getReactor().removeSystemEventTrigger(('before', 'shutdown',
                                            (function, (), {})))

def callDuringShutdown(function):
    """Add a function to be called during shutdown.

    These functions ought to shut down the event loop -- stopping
    thread pools, closing down all connections, etc.
    """
    _getReactor().addSystemEventTrigger('during', 'shutdown', function)


def removeCallDuringShutdown(function):
    _getReactor().removeSystemEventTrigger(('during', 'shutdown',
                                            (function, (), {})))

def callAfterShutdown(function):
    _getReactor().addSystemEventTrigger('after', 'shutdown', function)


def removeCallAfterShutdown(function):
    _getReactor().removeSystemEventTrigger(('after', 'shutdown',
                                            (function, (), {})))



class Delayeds:
    """Wrapper for twisted.python.delay.IDelayed objects, so they use IReactorTime."""

    def __init__(self):
        self.delayeds = []

    def addDelayed(self, d):
        self.delayeds.append(d)

    def removeDelayed(self, d):
        self.delayeds.remove(d)

    def timeout(self):
        """Return timeout until next run."""
        timeout = None
        for delay in self.delayeds:
            newTimeout = delay.timeout()
            if ((newTimeout is not None) and
                ((timeout is None) or
                 (newTimeout < timeout))):
                timeout = newTimeout
        return timeout

    def runUntilCurrent(self):
        """Run delayeds."""
        for d in self.delayeds:
            d.runUntilCurrent()


# delayeds backwards compatability - this will be done in base.ReactorBase
# once we get e.g. the task module to not call main.addDelayed on import
_delayeds = Delayeds()
addDelayed = _delayeds.addDelayed
removeDelayed = _delayeds.removeDelayed
