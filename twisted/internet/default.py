# -*- Python -*-
# $Id: default.py,v 1.3 2002/04/29 19:36:02 acapnotic Exp $
#
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

"""XXX - twisted.internet.default needs docstring
"""

from bisect import insort
from time import time
import os
import socket

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL
from twisted.internet.interfaces import IReactorProcess
from twisted.internet import main, tcp, udp, task
from twisted.python import log, threadable
from twisted.persisted import styles
from twisted.python.defer import DeferredList, Deferred
from twisted.python.runtime import platform

try:
    from twisted.internet import ssl
    sslEnabled = 1
except:
    sslEnabled = 0

from main import CONNECTION_LOST, CONNECTION_DONE

if platform.getType() != 'java':
    import select
    from errno import EINTR, EBADF


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


# global state for selector
reads = {}
writes = {}


class DefaultSelectReactor:
    __implements__ = IReactorCore, IReactorTime, IReactorUNIX, \
                     IReactorTCP, IReactorUDP, #\
                     # IReactorProcess
    if sslEnabled:
        __implements__ = __implements__ + (IReactorSSL,)

    installed = 0

    def __init__(self, installSignalHandlers=1):
        self._installSignalHandlers = installSignalHandlers
        self._eventTriggers = {}
        self._pendingTimedCalls = []
        threadable.whenThreaded(self.initThreads)

    # override in subclasses

    wakerInstalled = 0

    def initThreads(self):
        """Perform initialization required for threading.
        """
        if platform.getType() != 'java':
            self.installWaker()

    def installWaker(self):
        """Install a `waker' to allow other threads to wake up the IO thread.
        """
        if not self.wakerInstalled:
            self.wakerInstalled = 1
            self.waker = _Waker()
            self.addReader(self.waker)
            if self.installed:
                import main
                main.waker = self.waker

    def wakeUp(self):
        """Wake up the event loop."""
        if not threadable.isInIOThread():
            self.waker.wakeUp()

    def _preenDescriptors(self):
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

    def doSelect(self, timeout,
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
                self._preenDescriptors()
            except TypeError, te:
                # Something *totally* invalid (object w/o fileno, non-integral result)
                # was passed
                self._preenDescriptors()
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
                    self._preenDescriptors()
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
                    self.removeReader(selectable)
                    self.removeWriter(selectable)
                    try:
                        selectable.connectionLost()
                    except:
                        log.deferr()
                log.logOwner.disown(selectable)

    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read.
        """
        reads[reader] = 1

    def addWriter(self, writer):
        """Add a FileDescriptor for notification of data available to write.
        """
        writes[writer] = 1

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        if reads.has_key(reader):
            del reads[reader]

    def removeWriter(self, writer):
        """Remove a Selectable for notification of data available to write.
        """
        if writes.has_key(writer):
            del writes[writer]

    def removeAll(self):
        """Remove all readers and writers, and return list of Selectables."""
        readers = reads.keys()
        for reader in readers:
            if reads.has_key(reader):
                del reads[reader]
            if writes.has_key(reader):
                del writes[reader]
        return readers


    # Installation.

    def install(self):
        self.installed = 1

        # this stuff should be common to all reactors.
        import twisted.internet
        import sys
        twisted.internet.reactor = self
        sys.modules['twisted.internet.reactor'] = self

        # and this stuff is still yucky workarounds specific to the default case.
        main.addDelayed(self)

        # install stuff for backwards compatability
        main.addReader = self.addReader
        main.addWriter = self.addWriter
        main.removeWriter = self.removeWriter
        main.removeReader = self.removeReader
        main.removeAll = self.removeAll
        main.doSelect = self.doSelect
        if hasattr(self, "waker"):
            main.waker = self.waker
        main.wakeUp = self.wakeUp

    # IReactorCore

    def run(self):
        """See twisted.internet.interfaces.IReactorCore.run.
        """
        main.run(self._installSignalHandlers)


    def stop(self):
        """See twisted.internet.interfaces.IReactorCore.stop.
        """
        # TODO: fire 'shutdown' event.
        main.shutDown()


    def crash(self):
        """See twisted.internet.interfaces.IReactorCore.crash.
        """
        main.stopMainLoop()


    def iterate(self, delay=0):
        """See twisted.internet.interfaces.IReactorCore.iterate.
        """
        main.iterate(delay)

    def callFromThread(self, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.callFromThread.
        """
        apply(task.schedule, (callable,)+ args, kw)

    def fireSystemEvent(self, eventType):
        """See twisted.internet.interfaces.IReactorCore.fireSystemEvent.
        """
        sysEvtTriggers = self._eventTriggers.get(eventType)
        if not sysEvtTriggers:
            return
        defrList = []
        for callable, args, kw in sysEvtTriggers[0]:
            try:
                d = apply(callable, args, kw)
            except:
                log.deferr()
            else:
                if isinstance(d, Deferred):
                    defrList.append(d)
        if defrList:
            DeferredList(defrList).addBoth(self._cbContinueSystemEvent, eventType).arm()
        else:
            self._continueSystemEvent(eventType)


    def _cbContinueSystemEvent(self, result, eventType):
        self._continueSystemEvent(eventType)


    def _continueSystemEvent(self, eventType):
        sysEvtTriggers = self._eventTriggers.get(eventType)
        for callList in sysEvtTriggers[1], sysEvtTriggers[2]:
            for callable, args, kw in callList:
                try:
                    apply(callable, args, kw)
                except:
                    log.deferr()

    def addSystemEventTrigger(self, phase, eventType, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorCore.addSystemEventTrigger.
        """
        if self._eventTriggers.has_key(eventType):
            triglist = self._eventTriggers[eventType]
        else:
            triglist = [[], [], []]
            self._eventTriggers[eventType] = triglist
        evtList = triglist[{"before": 0, "during": 1, "after": 2}[phase]]
        evtList.append((callable, args, kw))
        return (phase, eventType, (callable, args, kw))

    def removeSystemEventTrigger(self, triggerID):
        """See twisted.internet.interfaces.IReactorCore.removeSystemEventTrigger.
        """
        phase, eventType, item = triggerID
        self._eventTriggers[eventType][{"before": 0,
                                        "during": 1,
                                        "after":  2}[phase]
                                       ].remove(item)


    # IReactorTime

    def callLater(self, seconds, callable, *args, **kw):
        """See twisted.internet.interfaces.IReactorTime.callLater.
        """
        tple = (time() + seconds, callable, args, kw)
        insort(self._pendingTimedCalls, tple)
        return tple

    def cancelCallLater(self, callID):
        """See twisted.internet.interfaces.IReactorTime.cancelCallLater.
        """
        self._pendingTimedCalls.remove(callID)


    # making myself look like a Delayed

    def timeout(self):
        if self._pendingTimedCalls:
            return max(self._pendingTimedCalls[0][0] - time(), 0)
        else:
            return None

    def runUntilCurrent(self):
        now = time()
        while self._pendingTimedCalls and (self._pendingTimedCalls[0][0] < now):
            seconds, func, args, kw = self._pendingTimedCalls.pop()
            try:
                apply(func, args, kw)
            except:
                log.deferr()


    # IReactorProcess ## XXX TODO!

    # IReactorUDP

    def listenUDP(self, port, factory, interface='', maxPacketSize=8192):
        """See twisted.internet.interfaces.IReactorUDP.listenUDP
        """
        return udp.Port(self, port, factory, interface, maxPacketSize)

    # IReactorUNIX

    def clientUNIX(self, address, protocol, timeout=30):
        """See twisted.internet.interfaces.IReactorUNIX.clientUNIX
        """
        return tcp.Client("unix", address, protocol, timeout=timeout)

    def listenUNIX(self, address, factory, backlog=5):
        """Listen on a UNIX socket.
        """
        return tcp.Port(address, factory, backlog=backlog)


    # IReactorTCP

    def listenTCP(self, port, factory, backlog=5, interface=''):
        """See twisted.internet.interfaces.IReactorTCP.listenTCP
        """
        return tcp.Port(port, factory, backlog, interface)

    def clientTCP(self, host, port, protocol, timeout=30):
        """See twisted.internet.interfaces.IReactorTCP.clientTCP
        """
        return tcp.Client(host, port, protocol, timeout)


    # IReactorSSL (sometimes, not implemented)

    def clientSSL(self, host, port, protocol, contextFactory, timeout=30,):
        return ssl.Client(host, port, protocol, contextFactory, timeout)

    def listenSSL(self, port, factory, contextFactory, backlog=5, interface=''):
        return ssl.Port(port, factory, contextFactory, backlog, interface)
