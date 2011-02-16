# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
A win32event based implementation of the Twisted main loop.

This requires pywin32 (formerly win32all) or ActivePython to be installed.

To install the event loop (and you should do this before any connections,
listeners or connectors are added)::

    from twisted.internet import win32eventreactor
    win32eventreactor.install()

Maintainer: Itamar Shtull-Trauring


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

# System imports
import time
import sys

from zope.interface import implements

# Win32 imports
from win32file import WSAEventSelect, FD_READ, FD_CLOSE, FD_ACCEPT, FD_CONNECT
from win32event import CreateEvent, MsgWaitForMultipleObjects
from win32event import WAIT_OBJECT_0, WAIT_TIMEOUT, QS_ALLINPUT, QS_ALLEVENTS

import win32gui

# Twisted imports
from twisted.internet import posixbase
from twisted.python import log, threadable, failure
from twisted.internet.interfaces import IReactorFDSet, IReactorProcess
from twisted.internet.interfaces import IReactorWin32Events

from twisted.internet._dumbwin32proc import Process


class Win32Reactor(posixbase.PosixReactorBase):
    """
    Reactor that uses Win32 event APIs.

    @ivar _reads: A dictionary mapping L{FileDescriptor} instances to a
        win32 event object used to check for read events for that descriptor.

    @ivar _writes: A dictionary mapping L{FileDescriptor} instances to a
        arbitrary value.  Keys in this dictionary will be given a chance to
        write out their data.

    @ivar _events: A dictionary mapping win32 event object to tuples of
        L{FileDescriptor} instances and event masks.
    """
    implements(IReactorFDSet, IReactorProcess, IReactorWin32Events)

    dummyEvent = CreateEvent(None, 0, 0, None)

    def __init__(self):
        self._reads = {}
        self._writes = {}
        self._events = {}
        posixbase.PosixReactorBase.__init__(self)


    def _makeSocketEvent(self, fd, action, why):
        """
        Make a win32 event object for a socket.
        """
        event = CreateEvent(None, 0, 0, None)
        WSAEventSelect(fd, event, why)
        self._events[event] = (fd, action)
        return event


    def addEvent(self, event, fd, action):
        """
        Add a new win32 event to the event loop.
        """
        self._events[event] = (fd, action)


    def removeEvent(self, event):
        """
        Remove an event.
        """
        del self._events[event]


    def addReader(self, reader):
        """
        Add a socket FileDescriptor for notification of data available to read.
        """
        if reader not in self._reads:
            self._reads[reader] = self._makeSocketEvent(
                reader, 'doRead', FD_READ | FD_ACCEPT | FD_CONNECT | FD_CLOSE)

    def addWriter(self, writer):
        """
        Add a socket FileDescriptor for notification of data available to write.
        """
        if writer not in self._writes:
            self._writes[writer] = 1

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        if reader in self._reads:
            del self._events[self._reads[reader]]
            del self._reads[reader]

    def removeWriter(self, writer):
        """Remove a Selectable for notification of data available to write.
        """
        if writer in self._writes:
            del self._writes[writer]

    def removeAll(self):
        """
        Remove all selectables, and return a list of them.
        """
        return self._removeAll(self._reads, self._writes)


    def getReaders(self):
        return self._reads.keys()


    def getWriters(self):
        return self._writes.keys()


    def doWaitForMultipleEvents(self, timeout):
        log.msg(channel='system', event='iteration', reactor=self)
        if timeout is None:
            #timeout = INFINITE
            timeout = 100
        else:
            timeout = int(timeout * 1000)

        if not (self._events or self._writes):
            # sleep so we don't suck up CPU time
            time.sleep(timeout / 1000.0)
            return

        canDoMoreWrites = 0
        for fd in self._writes.keys():
            if log.callWithLogger(fd, self._runWrite, fd):
                canDoMoreWrites = 1

        if canDoMoreWrites:
            timeout = 0

        handles = self._events.keys() or [self.dummyEvent]
        val = MsgWaitForMultipleObjects(handles, 0, timeout, QS_ALLINPUT | QS_ALLEVENTS)
        if val == WAIT_TIMEOUT:
            return
        elif val == WAIT_OBJECT_0 + len(handles):
            exit = win32gui.PumpWaitingMessages()
            if exit:
                self.callLater(0, self.stop)
                return
        elif val >= WAIT_OBJECT_0 and val < WAIT_OBJECT_0 + len(handles):
            fd, action = self._events[handles[val - WAIT_OBJECT_0]]
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

    def spawnProcess(self, processProtocol, executable, args=(), env={}, path=None, uid=None, gid=None, usePTY=0, childFDs=None):
        """Spawn a process."""
        if uid is not None:
            raise ValueError("Setting UID is unsupported on this platform.")
        if gid is not None:
            raise ValueError("Setting GID is unsupported on this platform.")
        if usePTY:
            raise ValueError("PTYs are unsupported on this platform.")
        if childFDs is not None:
            raise ValueError(
                "Custom child file descriptor mappings are unsupported on "
                "this platform.")
        args, env = self._checkProcessArgs(args, env)
        return Process(self, processProtocol, executable, args, env, path)


def install():
    threadable.init(1)
    r = Win32Reactor()
    import main
    main.installReactor(r)


__all__ = ["Win32Reactor", "install"]
