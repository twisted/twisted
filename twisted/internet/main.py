
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

# Twisted Import
from twisted.python.runtime import platform

if platform.getType() != 'java':
    import signal


import sys
import socket
CONNECTION_LOST = -1
CONNECTION_DONE = -2

theApplication = None

# Twisted Imports

from twisted.python import threadable, log
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
    global running, interruptCountdown, shuttingDown
    if not shuttingDown:
        if threadable.threaded:
            removeReader(waker)
        shuttingDown = 1
        log.msg('Starting shutdown sequence.')
        defrList = []
        for callback in beforeShutdown:
            try:
                d = callback()
            except:
                log.deferr()
            else:
                if isinstance(d, Deferred):
                    defrList.append(d)
        if defrList:
            DeferredList(defrList).addCallbacks(stopMainLoop, stopMainLoop).arm()
        else:
            stopMainLoop()
    elif interruptCountdown > 0:
        log.msg('Raising exception in %s more interrupts!' % interruptCountdown)
        interruptCountdown = interruptCountdown - 1
    else:
        stopMainLoop()
        raise RuntimeError("Shut down exception!")

def stopMainLoop(*ignored):
    global running
    running = 0
    log.msg("Stopping main loop.")


def handleSignals():
    """Install the signal handlers for the Twisted event loop."""
    signal.signal(signal.SIGINT, shutDown)
    signal.signal(signal.SIGTERM, shutDown)

    # Catch Ctrl-Break in windows (only available in 2.2b1 onwards)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutDown)

    if platform.getType() == 'posix':
        signal.signal(signal.SIGCHLD, process.reapProcess)


def run(installSignalHandlers=1):
    """Run input/output and dispatched/delayed code.

    This call \"never\" returns.  It is the main loop which runs delayed timers
    (see twisted.python.delay and addDelayed), and the I/O monitor (doSelect).

    """
    # now this is an ugly hack - make sure that we have a reactor installed
    import twisted.internet
    if not twisted.internet.reactor:
        import default
        reactor = default.SelectReactor()
        reactor.install()
    self = twisted.internet.reactor
    
    global running
    running = 1
    threadable.registerAsIOThread()

    callDuringShutdown(disconnectAll)

    if installSignalHandlers:
        handleSignals()

    for function in _whenRunning:
        function()
    _whenRunning[:] = []
    try:
        try:
            while running:
                # Advance simulation time in delayed event
                # processors.
                self.runUntilCurrent()
                timeout = self.timeout()                
                self.doIteration(running and timeout)
        except:
            log.msg("Unexpected error in main loop.")
            log.deferr()
            shutDown()
            raise
        else:
            log.msg('Main loop terminated.')

    finally:
        for callback in duringShutdown + afterShutdown:
            try:
                callback()
            except:
                log.deferr()


def disconnectAll():
    """Disconnect every reader, and writer in the system.
    """
    selectables = removeAll()
    for reader in selectables:
        log.logOwner.own(reader)
        try:
            reader.connectionLost()
        except:
            log.deferr()
        log.logOwner.disown(reader)

_whenRunning = []

def callWhenRunning(function):
    """Add a function to be called when the system starts running.

    If the system is already running, then the function runs immediately.  If
    the system has not yet started running, the function will be queued to get
    run when the mainloop starts.
    """
    if running:
        function()
    else:
        _whenRunning.append(function)

def callBeforeShutdown(function):
    """Add a function to be called before shutdown begins.

    These functions are tasks to be performed in order to run a
    "clean" shutdown.  This may involve tasks that keep the mainloop
    running, so any function registered in this list may return a
    Deferred, which will delay the actual shutdown until later.
    """
    beforeShutdown.append(function)

def removeCallBeforeShutdown(function):
    """Remove a function registered with callBeforeShutdown.
    """
    beforeShutdown.remove(function)

def callDuringShutdown(function):
    """Add a function to be called during shutdown.

    These functions ought to shut down the event loop -- stopping
    thread pools, closing down all connections, etc.
    """
    duringShutdown.append(function)

def removeCallDuringShutdown(function):
    duringShutdown.remove(function)

def callAfterShutdown(function):
    afterShutdown.append(function)

def removeCallAfterShutdown(function):
    duringShutdown.remove(function)


# Sibling Import
import process

# Work on Jython
if platform.getType() == 'java':
    import jnternet

# backward compatibility stuff
import app
Application = app.Application


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
        timeout = 1.0
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


# delayeds backwards compatability - this will be done in default.ReactorBase
# once we get e.g. the task module to not call main.addDelayed on import
_delayeds = Delayeds()
addDelayed = _delayeds.addDelayed
removeDelayed = _delayeds.removeDelayed

