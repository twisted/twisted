# -*- Python -*-
# $Id: default.py,v 1.13 2002/05/28 01:03:17 spiv Exp $
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
from time import time, sleep
import os
import socket
import signal

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL
from twisted.internet.interfaces import IReactorProcess
from twisted.internet import main

from twisted.internet import main, tcp, udp, task, process
from twisted.python import log, threadable
from twisted.persisted import styles
from twisted.python.runtime import platform

from twisted.internet.base import ReactorBase

try:
    from twisted.internet import ssl
    sslEnabled = 1
except:
    sslEnabled = 0

from main import CONNECTION_LOST, CONNECTION_DONE

if platform.getType() != 'java':
    import select
    from errno import EINTR, EBADF

class PosixReactorBase(ReactorBase):
    """A basis for reactors that use file descriptors.
    """
    __implements__ = (ReactorBase.__implements__, IReactorUNIX,
                      IReactorTCP, IReactorUDP) # IReactorProcess

    if sslEnabled:
        __implements__ = __implements__ + (IReactorSSL,)

    def __init__(self, installSignalHandlers=1):
        ReactorBase.__init__(self)
        self._installSignalHandlers = installSignalHandlers

    def _handleSignals(self):
        """Install the signal handlers for the Twisted event loop."""
        signal.signal(signal.SIGINT, self.sigInt)
        signal.signal(signal.SIGTERM, self.sigTerm)

        # Catch Ctrl-Break in windows (only available in 2.2b1 onwards)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self.sigBreak)

        if platform.getType() == 'posix':
            signal.signal(signal.SIGCHLD, process.reapProcess)

    def startRunning(self):
        threadable.registerAsIOThread()
        self.fireSystemEvent('startup')
        if self._installSignalHandlers:
            self._handleSignals()
        self.running = 1

    def run(self):
        self.startRunning()
        self.mainLoop()

    def mainLoop(self):
        while self.running:
            try:
                while self.running:
                    # Advance simulation time in delayed event
                    # processors.
                    self.runUntilCurrent()
                    t2 = self.timeout()
                    t = self.running and t2
                    # print self, 'running ', t, ' ', t2, ' ',self._pendingTimedCalls
                    self.doIteration(t)
            except:
                log.msg("Unexpected error in main loop.")
                log.deferr()
            else:
                log.msg('Main loop terminated.')


    def installWaker(self):
        """Install a `waker' to allow other threads to wake up the IO thread.
        """
        if not self.wakerInstalled:
            self.wakerInstalled = 1
            self.waker = _Waker()
            self.addReader(self.waker)

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
        p = tcp.Port(port, factory, backlog, interface)
        p.startListening()
        return p

    def clientTCP(self, host, port, protocol, timeout=30):
        """See twisted.internet.interfaces.IReactorTCP.clientTCP
        """
        return tcp.Client(host, port, protocol, timeout)


    def spawnProcess(self, processProtocol, executable, args=(), env={}, path=None):
        if platform.getType() == 'posix':
            return process.Process(executable, args, env, path, processProtocol)
        else:
            raise NotImplementedError, "process only available in this reactor on POSIX"

    # IReactorSSL (sometimes, not implemented)

    def clientSSL(self, host, port, protocol, contextFactory, timeout=30,):
        return ssl.Client(host, port, protocol, contextFactory, timeout)

    def listenSSL(self, port, factory, contextFactory, backlog=5, interface=''):
        return ssl.Port(port, factory, contextFactory, backlog, interface)



class _Win32Waker(log.Logger, styles.Ephemeral):
    """I am a workaround for the lack of pipes on win32.

    I am a pair of connected sockets which can wake up the main loop
    from another thread.
    """

    disconnected = 0
    
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

    def connectionLost(self):
        self.r.close()
        self.w.close()


class _UnixWaker(log.Logger, styles.Ephemeral):
    """This class provides a simple interface to wake up the select() loop.

    This is necessary only in multi-threaded programs.
    """

    disconnected = 0
    
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


def win32select(r, w, e, timeout=None):
    """Win32 select wrapper."""
    if not r and not w:
        # windows select() exits immediately when no sockets
        if timeout == None:
            timeout = 0.1
        else:
            timeout = min(timeout, 0.001)
        sleep(timeout)
        return [], [], []
    r, w, e = select.select(r, w, w, timeout)
    return r, w+e, []

if platform.getType() == "win32":
    _select = win32select
else:
    _select = select.select


class SelectReactor(PosixReactorBase):
    """A select() based reactor - runs on all POSIX platforms and on Win32.
    """

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
                r, w, ignored = _select(reads.keys(),
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

    doIteration = doSelect
    
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





def install():
    # Replace 'main' methods with my own
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = SelectReactor(1)
    main.installReactor(reactor)

