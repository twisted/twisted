# -*- test-case-name: twisted.test.test_internet -*-
# $Id: default.py,v 1.90 2004/01/06 22:35:22 warner Exp $
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

"""Default reactor base classes, and a select() based reactor.

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

from bisect import insort
from time import time, sleep
import os
import socket
import sys
import warnings

from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorUNIX, IReactorUNIXDatagram
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL, IReactorArbitrary
from twisted.internet.interfaces import IReactorProcess, IReactorFDSet, IReactorMulticast
from twisted.internet import main, error, protocol, interfaces
from twisted.internet import tcp, udp, defer

from twisted.python import log, threadable, failure
from twisted.persisted import styles
from twisted.python.runtime import platformType, platform

from twisted.internet.base import ReactorBase

try:
    from twisted.internet import ssl
    sslEnabled = True
except ImportError:
    sslEnabled = False

try:
    from twisted.internet import unix
    unixEnabled = True
except ImportError:
    unixEnabled = False

from main import CONNECTION_LOST

if platformType != 'java':
    import select
    from errno import EINTR, EBADF

if platformType == 'posix':
    import process

if platformType == "win32":
    try:
        import win32process
    except ImportError:
        win32process = None


class PosixReactorBase(ReactorBase):
    """A basis for reactors that use file descriptors.
    """
    __implements__ = (ReactorBase.__implements__, IReactorArbitrary,
                      IReactorTCP, IReactorUDP, IReactorMulticast)

    if sslEnabled:
        __implements__ = __implements__ + (IReactorSSL,)
    if unixEnabled:
        __implements__ = __implements__ + (IReactorUNIX, IReactorUNIXDatagram, IReactorProcess)

    def __init__(self):
        ReactorBase.__init__(self)
        if self.usingThreads or platformType == "posix":
            self.installWaker()

    def _handleSignals(self):
        """Install the signal handlers for the Twisted event loop."""
        import signal
        signal.signal(signal.SIGINT, self.sigInt)
        signal.signal(signal.SIGTERM, self.sigTerm)

        # Catch Ctrl-Break in windows (only available in Python 2.2 and up)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self.sigBreak)

        if platformType == 'posix':
            signal.signal(signal.SIGCHLD, self._handleSigchld)

    def _handleSigchld(self, signum, frame):
        """Reap all processes on SIGCHLD.

        This gets called on SIGCHLD. We do no processing inside a signal
        handler, as the calls we make here could occur between any two
        python bytecode instructions. Deferring processing to the next
        eventloop round prevents us from violating the state constraints
        of arbitrary classes. Note that a Reactor must be able to accept
        callLater calls at any time, even interleaved inside it's own
        methods; it must block SIGCHLD if it is unable to guarantee this.
        """
        self.callLater(0, process.reapAllProcesses)
        self.wakeUp()

    def startRunning(self, installSignalHandlers=1):
        threadable.registerAsIOThread()
        self.fireSystemEvent('startup')
        if installSignalHandlers:
            self._handleSignals()
        self.running = 1

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
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
                    self.doIteration(t)
            except:
                log.msg("Unexpected error in main loop.")
                log.deferr()
            else:
                log.msg('Main loop terminated.')


    def installWaker(self):
        """Install a `waker' to allow threads and signals to wake up the IO thread.

        We use the self-pipe trick (http://cr.yp.to/docs/selfpipe.html) to wake
        the reactor. On Windows we use a pair of sockets.
        """
        if not self.waker:
            self.waker = _Waker(self)
            self.addReader(self.waker)


    # IReactorProcess

    def spawnProcess(self, processProtocol, executable, args=(),
                     env={}, path=None,
                     uid=None, gid=None, usePTY=0, childFDs=None):
        p = platform.getType()
        if p == 'posix':
            if usePTY:
                assert childFDs == None
                return process.PTYProcess(self, executable, args, env, path,
                                          processProtocol, uid, gid, usePTY)
            else:
                return process.Process(self, executable, args, env, path,
                                       processProtocol, uid, gid, childFDs)
        # This is possible, just needs work - talk to itamar if you want this.
        #elif p == "win32":
        #    if win32process:
        #        threadable.init(1)
        #        import win32eventreactor
        #        return win32eventreactor.Process(self, processProtocol, executable, args, env, path)
        #    else:
        #        raise NotImplementedError, "process not available since win32all is not installed"
        else:
            raise NotImplementedError, "process only available in this " \
                  "reactor on POSIX, use win32eventreactor on Windows"


    # IReactorUDP

    def listenUDP(self, port, protocol, interface='', maxPacketSize=8192):
        """Connects a given L{DatagramProtocol} to the given numeric UDP port.

        EXPERIMENTAL.

        @returns: object conforming to L{IListeningPort}.
        """
        p = udp.Port(port, protocol, interface, maxPacketSize, self)
        p.startListening()
        return p

    def connectUDP(self, remotehost, remoteport, protocol, localport=0,
                  interface='', maxPacketSize=8192):
        """DEPRECATED.

        Connects a L{ConnectedDatagramProtocol} instance to a UDP port.
        """
        warnings.warn("use listenUDP and then transport.connect().", DeprecationWarning, stacklevel=2)
        p = udp.ConnectedPort((remotehost, remoteport), localport, protocol, interface, maxPacketSize, self)
        p.startListening()
        return p


    # IReactorMulticast

    def listenMulticast(self, port, protocol, interface='', maxPacketSize=8192):
        """Connects a given DatagramProtocol to the given numeric UDP port.

        EXPERIMENTAL.

        @returns: object conforming to IListeningPort.
        """
        p = udp.MulticastPort(port, protocol, interface, maxPacketSize, self)
        p.startListening()
        return p

    def connectMulticast(self, remotehost, remoteport, protocol, localport=0,
                         interface='', maxPacketSize=8192):
        """Connects a ConnectedDatagramProtocol instance to a UDP port.

        EXPERIMENTAL.
        """
        warnings.warn("use listenMulticast and then transport.connect().", DeprecationWarning, stacklevel=2)
        p = udp.ConnectedMulticastPort((remotehost, remoteport), localport, protocol, interface, maxPacketSize, self)
        p.startListening()
        return p


    # IReactorUNIX

    def connectUNIX(self, address, factory, timeout=30, checkPID=0):
        """@see: twisted.internet.interfaces.IReactorUNIX.connectUNIX
        """
        assert unixEnabled, "UNIX support is not present"
        c = unix.Connector(address, factory, timeout, self, checkPID)
        c.connect()
        return c

    def listenUNIX(self, address, factory, backlog=5, mode=0666, wantPID=0):
        """@see: twisted.internet.interfaces.IReactorUNIX.listenUNIX
        """
        assert unixEnabled, "UNIX support is not present"
        p = unix.Port(address, factory, backlog, mode, self, wantPID)
        p.startListening()
        return p


    # IReactorUNIXDatagram

    def listenUNIXDatagram(self, address, protocol, maxPacketSize=8192, mode=0666):
        """Connects a given L{DatagramProtocol} to the given path.

        EXPERIMENTAL.

        @returns: object conforming to L{IListeningPort}.
        """
        assert unixEnabled, "UNIX support is not present"
        p = unix.DatagramPort(address, protocol, maxPacketSize, mode, self)
        p.startListening()
        return p

    def connectUNIXDatagram(self, address, protocol, maxPacketSize=8192, mode=0666, bindAddress=None):
        """Connects a L{ConnectedDatagramProtocol} instance to a path.

        EXPERIMENTAL.
        """
        assert unixEnabled, "UNIX support is not present"
        p = unix.ConnectedDatagramPort(address, protocol, maxPacketSize, mode, bindAddress, self)
        p.startListening()
        return p


    # IReactorTCP

    def listenTCP(self, port, factory, backlog=5, interface=''):
        """@see: twisted.internet.interfaces.IReactorTCP.listenTCP
        """
        p = tcp.Port(port, factory, backlog, interface, self)
        p.startListening()
        return p

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """@see: twisted.internet.interfaces.IReactorTCP.connectTCP
        """
        c = tcp.Connector(host, port, factory, timeout, bindAddress, self)
        c.connect()
        return c

    # IReactorSSL (sometimes, not implemented)

    def connectSSL(self, host, port, factory, contextFactory, timeout=30, bindAddress=None):
        """@see: twisted.internet.interfaces.IReactorSSL.connectSSL
        """
        assert sslEnabled, "SSL support is not present"
        c = ssl.Connector(host, port, factory, contextFactory, timeout, bindAddress, self)
        c.connect()
        return c

    def listenSSL(self, port, factory, contextFactory, backlog=5, interface=''):
        """@see: twisted.internet.interfaces.IReactorSSL.listenSSL
        """
        assert sslEnabled, "SSL support is not present"
        p = ssl.Port(port, factory, contextFactory, backlog, interface, self)
        p.startListening()
        return p

    # IReactorArbitrary
    def listenWith(self, portType, *args, **kw):
        kw['reactor'] = self
        p = portType(*args, **kw)
        p.startListening()
        return p

    def connectWith(self, connectorType, *args, **kw):
        kw['reactor'] = self
        c = connectorType(*args, **kw)
        c.connect()
        return c


class _Win32Waker(log.Logger, styles.Ephemeral):
    """I am a workaround for the lack of pipes on win32.

    I am a pair of connected sockets which can wake up the main loop
    from another thread.
    """

    disconnected = 0

    def __init__(self, reactor):
        """Initialize.
        """
        log.msg("starting waker")
        self.reactor = reactor
        # Following select_trigger (from asyncore)'s example;
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.setsockopt(socket.IPPROTO_TCP, 1, 1)
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        client.connect(server.getsockname())
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
        try:
            self.r.recv(8192)
        except socket.error:
            pass

    def connectionLost(self, reason):
        self.r.close()
        self.w.close()
        self.reactor.waker = None


class _UnixWaker(log.Logger, styles.Ephemeral):
    """This class provides a simple interface to wake up the select() loop.

    This is used by threads or signals to wake up the event loop.
    """

    disconnected = 0

    def __init__(self, reactor):
        """Initialize.
        """
        self.reactor = reactor
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
        if hasattr(self, "o"):
            self.o.write('x')
            self.o.flush()

    def connectionLost(self, reason):
        """Close both ends of my pipe.
        """
        if not hasattr(self, "o"):
            return
        try:
            self.i.close()
            self.o.close()
        except IOError:
            pass
        del self.i
        del self.o
        self.reactor.waker = None


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
            timeout = 0.01
        else:
            timeout = min(timeout, 0.001)
        sleep(timeout)
        return [], [], []
    # windows doesn't process 'signals' inside select(), so we set a max
    # time or ctrl-c will never be recognized
    if timeout == None or timeout > 0.5:
        timeout = 0.5
    r, w, e = select.select(r, w, w, timeout)
    return r, w+e, []

if platform.getType() == "win32":
    _select = win32select
else:
    _select = select.select

# Exceptions that doSelect might return frequently
_NO_FILENO = error.ConnectionFdescWentAway('Handler has no fileno method')
_NO_FILEDESC = error.ConnectionFdescWentAway('Filedescriptor went away')

class SelectReactor(PosixReactorBase):
    """A select() based reactor - runs on all POSIX platforms and on Win32.
    """

    __implements__ = (PosixReactorBase.__implements__, IReactorFDSet)

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
                 writes=writes):
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
                log.err()
                self._preenDescriptors()
            except TypeError, te:
                # Something *totally* invalid (object w/o fileno, non-integral
                # result) was passed
                log.err()
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
        _drdw = self._doReadOrWrite
        _logrun = log.callWithLogger
        for selectables, method, dict in ((r, "doRead", reads),
                                          (w,"doWrite", writes)):
            hkm = dict.has_key
            for selectable in selectables:
                # if this was disconnected in another thread, kill it.
                if not hkm(selectable):
                    continue
                # This for pausing input when we're not ready for more.
                _logrun(selectable, _drdw, selectable, method, dict)

    doIteration = doSelect

    def _doReadOrWrite(self, selectable, method, dict, faildict={
        error.ConnectionDone: failure.Failure(error.ConnectionDone()),
        error.ConnectionLost: failure.Failure(error.ConnectionLost())
        }):
        try:
            why = getattr(selectable, method)()
            handfn = getattr(selectable, 'fileno', None)
            if not handfn:
                why = _NO_FILENO
            elif handfn() == -1:
                why = _NO_FILEDESC
        except:
            why = sys.exc_info()[1]
            log.err()
        if why:
            self.removeReader(selectable)
            self.removeWriter(selectable)
            f = faildict.get(why.__class__)
            if f:
                selectable.connectionLost(f)
            else:
                selectable.connectionLost(failure.Failure(why))

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
        self.waker = None
        return readers


def install():
    """Configure the twisted mainloop to be run using the select() reactor.
    """
    reactor = SelectReactor()
    main.installReactor(reactor)


__all__ = ["install", "PosixReactorBase", "SelectReactor"]
