
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
    import select, signal
    from errno import EINTR, EBADF

import sys
import socket
CONNECTION_LOST = -1
CONNECTION_DONE = -2

theApplication = None

# Twisted Imports

from twisted.python import threadable, log, delay
from twisted.persisted import styles
from twisted.python.defer import Deferred, DeferredList

# Sibling Imports

theTimeouts = delay.Time() # A delay for non-peristent delayed actions

def addTimeout(method, seconds):
    """Add a method which will time out after a given interval.

    The given method will always time out before a server shuts down,
    and will never persist.
    """
    theTimeouts.runLater(seconds, method)


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

reads = {}
writes = {}
running = None
shuttingDown = None
delayeds = [theTimeouts]
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

def runUntilCurrent():
    """Run all delayed loops and return a timeout for when the next call expects to be made.
    """
    # This code is duplicated for efficiency later.
    timeout = None
    for delayed in delayeds:
        delayed.runUntilCurrent()
    for delay in delayeds:
        newTimeout = delayed.timeout()
        if ((newTimeout is not None) and
            ((timeout is None) or
             (newTimeout < timeout))):
            timeout = newTimeout
    return timeout

def _preenDescriptors():
    log.msg("Malformed file descriptor found.  Preening lists.")
    readers = reads.keys()
    writers = writes.keys()
    reads.clear()
    writes.clear()
    for selDict, selList in ((reads, readers), (writes, writers)):
        for selectable in selList:
            try:
                select.select([selectable], [selectable], [selectable], 0)
            except:
                log.msg("bad descriptor %s" % selectable)
            else:
                selDict[selectable] = 1


def doSelect(timeout,
             # Since this loop should really be as fast as possible,
             # I'm caching these global attributes so the interpreter
             # will hit them in the local namespace.
             reads=reads,
             writes=writes,
             rhk=reads.has_key,
             whk=writes.has_key):
    """Run one iteration of the I/O monitor loop.

    This will run all selectables who had input or output readiness
    waiting for them.
    """
    while 1:
        try:
            r, w, ignored = select.select(reads.keys(),
                                          writes.keys(),
                                          [], timeout)
            break
        except ValueError, ve:
            # Possibly a file descriptor has gone negative?
            _preenDescriptors()
        except TypeError, te:
            # Something *totally* invalid (object w/o fileno, non-integral result)
            # was passed
            _preenDescriptors()
        except select.error,se:
            # select(2) encountered an error
            if se.args[0] in (0, 2):
                # windows does this if it got an empty list
                if (not reads) and (not writes):
                    return
                else:
                    raise
            elif se.args[0] == EINTR:
                return
            elif se.args[0] == EBADF:
                _preenDescriptors()
            else:
                # OK, I really don't know what's going on.  Blow up.
                raise
    for selectables, method, dict in ((r, "doRead", reads),
                                      (w,"doWrite", writes)):
        hkm = dict.has_key
        for selectable in selectables:
            # if this was disconnected in another thread, kill it.
            if not hkm(selectable):
                continue
            # This for pausing input when we're not ready for more.
            log.logOwner.own(selectable)
            try:
                why = getattr(selectable, method)()
                handfn = getattr(selectable, 'fileno', None)
                if not handfn or handfn() == -1:
                    why = CONNECTION_LOST
            except:
                log.deferr()
                why = CONNECTION_LOST
            if why:
                removeReader(selectable)
                removeWriter(selectable)
                try:
                    selectable.connectionLost()
                except:
                    log.deferr()
            log.logOwner.disown(selectable)


def iterate(timeout=0.):
    """Do one iteration of the main loop.

    I will run any simulated (delayed) code, and process any pending I/O.
    I will not block.  This is meant to be called from a high-freqency
    updating loop function like the frame-processing function of a game.
    """
    for delayed in delayeds:
        delayed.runUntilCurrent()
    doSelect(timeout)


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
                timeout = None
                for delayed in delayeds:
                    delayed.runUntilCurrent()
                for delayed in delayeds:
                    newTimeout = delayed.timeout()
                    if ((newTimeout is not None) and
                        ((timeout is None) or
                         (newTimeout < timeout))):
                        timeout = newTimeout

                doSelect(running and timeout)
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

def addDelayed(delayed):
    """Add an object implementing the IDelayed interface to the event loop.

    See twisted.python.delay.IDelayed for more details.
    """
    delayeds.append(delayed)

def removeDelayed(delayed):
    """Remove a Delayed object from the event loop.
    """
    delayeds.remove(delayed)

def addReader(reader):
    """Add a FileDescriptor for notification of data available to read.
    """
    reads[reader] = 1

def addWriter(writer):
    """Add a FileDescriptor for notification of data available to write.
    """
    writes[writer] = 1

def removeReader(reader):
    """Remove a Selectable for notification of data available to read.
    """
    if reads.has_key(reader):
        del reads[reader]

def removeWriter(writer):
    """Remove a Selectable for notification of data available to write.
    """
    if writes.has_key(writer):
        del writes[writer]

def removeAll():
    """Remove all readers and writers, and return list of Selectables."""
    readers = reads.keys()
    for reader in readers:
        if reads.has_key(reader):
            del reads[reader]
        if writes.has_key(reader):
            del writes[reader]
    return readers


class _Win32Waker(styles.Ephemeral):
    """I am a workaround for the lack of pipes on win32.

    I am a pair of connected sockets which can wake up the main loop
    from another thread.
    """
    def __init__(self):
        """Initialize.
        """
        # Following select_trigger (from asyncore)'s example;
        address = ("127.0.0.1",19939)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.setsockopt(socket.IPPROTO_TCP, 1, 1)
        server.bind(address)
        server.listen(1)
        client.connect(address)
        reader, clientaddr = server.accept()
        client.setblocking(1)
        reader.setblocking(0)
        self.r = reader
        self.w = client
        self.fileno = self.r.fileno

    def wakeUp(self):
        """Send a byte to my connection.
        """
        self.w.send('x')

    def doRead(self):
        """Read some data from my connection.
        """
        self.r.recv(8192)

class _UnixWaker(styles.Ephemeral):
    """This class provides a simple interface to wake up the select() loop.

    This is necessary only in multi-threaded programs.
    """
    def __init__(self):
        """Initialize.
        """
        i, o = os.pipe()
        self.i = os.fdopen(i,'r')
        self.o = os.fdopen(o,'w')
        self.fileno = self.i.fileno

    def doRead(self):
        """Read one byte from the pipe.
        """
        self.i.read(1)

    def wakeUp(self):
        """Write one byte to the pipe, and flush it.
        """
        try:
            self.o.write('x')
            self.o.flush()
        except ValueError:
            # o has been closed
            pass

    def connectionLost(self):
        """Close both ends of my pipe.
        """
        self.i.close()
        self.o.close()

if platform.getType() == 'posix':
    _Waker = _UnixWaker
elif platform.getType() == 'win32':
    _Waker = _Win32Waker

def wakeUp():
    if not threadable.isInIOThread():
        waker.wakeUp()


wakerInstalled = 0

def installWaker():
    """Install a `waker' to allow other threads to wake up the IO thread.
    """
    global waker, wakerInstalled
    if not wakerInstalled:
        wakerInstalled = 1
        waker = _Waker()
        addReader(waker)

def initThreads():
    """Perform initialization required for threading.
    """
    if platform.getType() != 'java':
        installWaker()

threadable.whenThreaded(initThreads)
# Sibling Import
import process

# Work on Jython
if platform.getType() == 'java':
    import jnternet

# backward compatibility stuff
import app
Application = app.Application
