# -*- test-case-name: twisted.test.test_app -*-
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

"""Backwards compatability, and utility functions.

In general, this module should not be used, other than by reactor authors
who need to use the 'installReactor' method.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import socket
import warnings

# Twisted Imports

from twisted.python import log
from twisted.python import threadable, failure
from twisted.python.runtime import platform
from twisted.persisted import styles
from twisted.python.components import implements
from twisted.internet.interfaces import IReactorFDSet, IReactorCore
from twisted.internet.interfaces import IReactorTime, IReactorUNIX
import error

CONNECTION_DONE = error.ConnectionDone('Connection done')
CONNECTION_LOST = error.ConnectionLost('Connection lost')


running = None
shuttingDown = None
beforeShutdown = []
duringShutdown = []
afterShutdown = []
interruptCountdown = 5

def shutDown(*ignored):
    """Run all shutdown callbacks (save all running Applications) and exit.

    This is called by various signal handlers which should cause
    the process to exit.  It can also be called directly in order
    to trigger a clean shutdown.
    """
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    _getReactor().stop()

def stopMainLoop(*ignored):
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    global running
    running = 0
    log.msg("Stopping main loop.")

def _getReactor():
    from twisted.internet import reactor
    return reactor


def run(installSignalHandlers=1):
    """Run input/output and dispatched/delayed code. Don't call this directly.

    This call \"never\" returns.  
    """
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    global running
    running = 1
    _getReactor().run(installSignalHandlers=installSignalHandlers)


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

    # IReactorCore
    if implements(reactor, IReactorCore):
        iterate = reactor.iterate

    # IReactorFDSet
    if implements(reactor, IReactorFDSet):
        addReader = reactor.addReader
        addWriter = reactor.addWriter
        removeWriter = reactor.removeWriter
        removeReader = reactor.removeReader

    # IReactorTime
    if implements(reactor, IReactorTime):
        def addTimeout(m, t, f=reactor.callLater):
            warnings.warn("main.addTimeout is deprecated, use reactor.callLater instead.")
            f(t, m)

    # ???
    if hasattr(reactor, "wakeUp"):
        wakeUp = reactor.wakeUp



def callWhenRunning(function):
    """Add a function to be called when the system starts running.

    If the system is already running, then the function runs immediately.  If
    the system has not yet started running, the function will be queued to get
    run when the mainloop starts.
    """
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
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
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    _getReactor().addSystemEventTrigger('before', 'shutdown', function)

def removeCallBeforeShutdown(function):
    """Remove a function registered with callBeforeShutdown.
    """
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    _getReactor().removeSystemEventTrigger(('before', 'shutdown',
                                            (function, (), {})))

def callDuringShutdown(function):
    """Add a function to be called during shutdown.

    These functions ought to shut down the event loop -- stopping
    thread pools, closing down all connections, etc.
    """
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    _getReactor().addSystemEventTrigger('during', 'shutdown', function)


def removeCallDuringShutdown(function):
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    _getReactor().removeSystemEventTrigger(('during', 'shutdown',
                                            (function, (), {})))

def callAfterShutdown(function):
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    _getReactor().addSystemEventTrigger('after', 'shutdown', function)


def removeCallAfterShutdown(function):
    warnings.warn("Please use reactor methods instead of twisted.internet.main")
    _getReactor().removeSystemEventTrigger(('after', 'shutdown',
                                            (function, (), {})))


__all__ = ["CONNECTION_LOST", "CONNECTION_DONE", "installReactor"]
