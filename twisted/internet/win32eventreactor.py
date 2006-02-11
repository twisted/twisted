# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""A win32event based implementation of the Twisted main loop.

This requires win32all or ActivePython to be installed.

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}


LIMITATIONS:
 1. WaitForMultipleObjects and thus the event loop can only handle 64 objects.
 2. Process running has some problems (see Process docstring).


TODO:
 1. Event loop handling of writes is *very* problematic (this is causing failed tests).
    Switch to doing it the correct way, whatever that means (see below).
 2. Replace icky socket loopback waker with event based waker (use dummyEvent object)
 3. Switch everyone to using Free Software so we don't have to deal with proprietary APIs.


ALTERNATIVE SOLUTIONS:
 - IIRC, sockets can only be registered once. So we switch to a structure
   like the poll() reactor, thus allowing us to deal with write events in
   a decent fashion. This should allow us to pass tests, but we're still
   limited to 64 events.

Or:

 - Instead of doing a reactor, we make this an addon to the select reactor.
   The WFMO event loop runs in a separate thread. This means no need to maintain
   separate code for networking, 64 event limit doesn't apply to sockets,
   we can run processes and other win32 stuff in default event loop. The
   only problem is that we're stuck with the icky socket based waker.
   Another benefit is that this could be extended to support >64 events
   in a simpler manner than the previous solution.

The 2nd solution is probably what will get implemented.
"""

# Win32 imports
from win32file import WSAEventSelect, FD_READ, FD_WRITE, FD_CLOSE, \
                      FD_ACCEPT, FD_CONNECT
from win32event import CreateEvent, MsgWaitForMultipleObjects, \
                       WAIT_OBJECT_0, WAIT_TIMEOUT, INFINITE, QS_ALLINPUT, QS_ALLEVENTS
import win32api
import win32con
import win32event
import win32file
import win32pipe
import win32process
import win32security
import pywintypes
import msvcrt
import win32gui

# Twisted imports
from twisted.internet import abstract, posixbase, main, error
from twisted.python import log, threadable, failure, components
from twisted.internet.interfaces import IReactorFDSet, IReactorProcess, IProcessTransport

from twisted.internet._dumbwin32proc import Process

# System imports
import os
import threading
import Queue
import string
import time
import sys
from zope.interface import implements


# globals
reads = {}
writes = {}
events = {}


class Win32Reactor(posixbase.PosixReactorBase):
    """Reactor that uses Win32 event APIs."""

    implements(IReactorFDSet, IReactorProcess)

    dummyEvent = CreateEvent(None, 0, 0, None)

    def _makeSocketEvent(self, fd, action, why, events=events):
        """Make a win32 event object for a socket."""
        event = CreateEvent(None, 0, 0, None)
        WSAEventSelect(fd, event, why)
        events[event] = (fd, action)
        return event

    def addEvent(self, event, fd, action, events=events):
        """Add a new win32 event to the event loop."""
        events[event] = (fd, action)

    def removeEvent(self, event):
        """Remove an event."""
        del events[event]

    def addReader(self, reader, reads=reads):
        """Add a socket FileDescriptor for notification of data available to read.
        """
        if not reads.has_key(reader):
            reads[reader] = self._makeSocketEvent(reader, 'doRead', FD_READ|FD_ACCEPT|FD_CONNECT|FD_CLOSE)

    def addWriter(self, writer, writes=writes):
        """Add a socket FileDescriptor for notification of data available to write.
        """
        if not writes.has_key(writer):
            writes[writer] = 1

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        if reads.has_key(reader):
            del events[reads[reader]]
            del reads[reader]

    def removeWriter(self, writer, writes=writes):
        """Remove a Selectable for notification of data available to write.
        """
        if writes.has_key(writer):
            del writes[writer]

    def removeAll(self):
        """Remove all selectables, and return a list of them."""
        return self._removeAll(reads, writes)

    def doWaitForMultipleEvents(self, timeout,
                                reads=reads,
                                writes=writes):
        log.msg(channel='system', event='iteration', reactor=self)
        if timeout is None:
            #timeout = INFINITE
            timeout = 100
        else:
            timeout = int(timeout * 1000)

        if not (events or writes):
            # sleep so we don't suck up CPU time
            time.sleep(timeout / 1000.0)
            return

        canDoMoreWrites = 0
        for fd in writes.keys():
            if log.callWithLogger(fd, self._runWrite, fd):
                canDoMoreWrites = 1

        if canDoMoreWrites:
            timeout = 0

        handles = events.keys() or [self.dummyEvent]
        val = MsgWaitForMultipleObjects(handles, 0, timeout, QS_ALLINPUT | QS_ALLEVENTS)
        if val == WAIT_TIMEOUT:
            return
        elif val == WAIT_OBJECT_0 + len(handles):
            exit = win32gui.PumpWaitingMessages()
            if exit:
                self.callLater(0, self.stop)
                return
        elif val >= WAIT_OBJECT_0 and val < WAIT_OBJECT_0 + len(handles):
            fd, action = events[handles[val - WAIT_OBJECT_0]]
            log.callWithLogger(fd, self._runAction, action, fd)

    def _runWrite(self, fd):
        closed = 0
        try:
            closed = fd.doWrite()
        except:
            closed = sys.exc_info()[1]
            log.deferr()

        if closed:
            self.removeReader(fd)
            self.removeWriter(fd)
            try:
                fd.connectionLost(failure.Failure(closed))
            except:
                log.deferr()
        elif closed is None:
            return 1

    def _runAction(self, action, fd):
        try:
            closed = getattr(fd, action)()
        except:
            closed = sys.exc_info()[1]
            log.deferr()

        if closed:
            self._disconnectSelectable(fd, closed, action == 'doRead')

    doIteration = doWaitForMultipleEvents

    def spawnProcess(self, processProtocol, executable, args=(), env={}, path=None, uid=None, gid=None, usePTY=0):
        """Spawn a process."""
        if uid is not None:
            raise ValueError("Setting UID is unsupported on this platform.")
        if gid is not None:
            raise ValueError("Setting GID is unsupported on this platform.")
        if usePTY:
            raise ValueError("PTYs are unsupported on this platform.")
        return Process(self, processProtocol, executable, args, env, path)

components.backwardsCompatImplements(Win32Reactor)


def install():
    threadable.init(1)
    r = Win32Reactor()
    import main
    main.installReactor(r)


__all__ = ["Win32Reactor", "install"]
