# -*- test-case-name: twisted.test.test_internet -*-
# $Id: default.py,v 1.90 2004/01/06 22:35:22 warner Exp $
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Posix reactor base class

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import warnings
import socket
import errno
import os
from zope.interface import implements, classImplements

from twisted.internet.interfaces import IReactorUNIX, IReactorUNIXDatagram
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorSSL, IReactorArbitrary
from twisted.internet.interfaces import IReactorProcess, IReactorMulticast
from twisted.internet.interfaces import IHalfCloseableDescriptor
from twisted.internet import error
from twisted.internet import tcp, udp

from twisted.python import log, threadable, failure, components, util
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

processEnabled = False
if platformType == 'posix':
    from twisted.internet import fdesc
    import process
    processEnabled = True

if platform.isWindows():
    try:
        import win32process
        processEnabled = True
    except ImportError:
        win32process = None


class _Win32Waker(log.Logger, styles.Ephemeral):
    """I am a workaround for the lack of pipes on win32.

    I am a pair of connected sockets which can wake up the main loop
    from another thread.
    """
    disconnected = 0

    def __init__(self, reactor):
        """Initialize.
        """
        self.reactor = reactor
        # Following select_trigger (from asyncore)'s example;
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.setsockopt(socket.IPPROTO_TCP, 1, 1)
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        client.connect(server.getsockname())
        reader, clientaddr = server.accept()
        client.setblocking(0)
        reader.setblocking(0)
        self.r = reader
        self.w = client
        self.fileno = self.r.fileno

    def wakeUp(self):
        """Send a byte to my connection.
        """
        try:
            util.untilConcludes(self.w.send, 'x')
        except socket.error, (err, msg):
            if err != errno.WSAEWOULDBLOCK:
                raise

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
    """This class provides a simple interface to wake up the event loop.

    This is used by threads or signals to wake up the event loop.
    """
    disconnected = 0

    i = None
    o = None

    def __init__(self, reactor):
        """Initialize.
        """
        self.reactor = reactor
        self.i, self.o = os.pipe()
        fdesc.setNonBlocking(self.i)
        fdesc.setNonBlocking(self.o)
        self.fileno = lambda: self.i

    def doRead(self):
        """Read some bytes from the pipe.
        """
        fdesc.readFromFD(self.fileno(), lambda data: None)

    def wakeUp(self):
        """Write one byte to the pipe, and flush it.
        """
        if self.o is not None:
            try:
                util.untilConcludes(os.write, self.o, 'x')
            except OSError, e:
                if e.errno != errno.EAGAIN:
                    raise

    def connectionLost(self, reason):
        """Close both ends of my pipe.
        """
        if not hasattr(self, "o"):
            return
        for fd in self.i, self.o:
            try:
                os.close(fd)
            except IOError:
                pass
        del self.i, self.o
        self.reactor.waker = None


if platformType == 'posix':
    _Waker = _UnixWaker
elif platformType == 'win32':
    _Waker = _Win32Waker


class PosixReactorBase(ReactorBase):
    """A basis for reactors that use file descriptors.
    """
    implements(IReactorArbitrary, IReactorTCP, IReactorUDP, IReactorMulticast)

    def __init__(self):
        ReactorBase.__init__(self)
        if self.usingThreads or platformType == "posix":
            self.installWaker()

    def _handleSignals(self):
        """Install the signal handlers for the Twisted event loop."""
        try:
            import signal
        except ImportError:
            log.msg("Warning: signal module unavailable -- not installing signal handlers.")
            return

        if signal.getsignal(signal.SIGINT) == signal.default_int_handler:
            # only handle if there isn't already a handler, e.g. for Pdb.
            signal.signal(signal.SIGINT, self.sigInt)
        signal.signal(signal.SIGTERM, self.sigTerm)

        # Catch Ctrl-Break in windows
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self.sigBreak)

        if platformType == 'posix':
            signal.signal(signal.SIGCHLD, self._handleSigchld)

    def _handleSigchld(self, signum, frame, _threadSupport=platform.supportsThreads()):
        """Reap all processes on SIGCHLD.

        This gets called on SIGCHLD. We do no processing inside a signal
        handler, as the calls we make here could occur between any two
        python bytecode instructions. Deferring processing to the next
        eventloop round prevents us from violating the state constraints
        of arbitrary classes.
        """
        if _threadSupport:
            self.callFromThread(process.reapAllProcesses)
        else:
            self.callLater(0, process.reapAllProcesses)

    def startRunning(self, installSignalHandlers=1):
        # Just in case we're started on a different thread than
        # we're made on
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

    def _disconnectSelectable(self, selectable, why, isRead, faildict={
        error.ConnectionDone: failure.Failure(error.ConnectionDone()),
        error.ConnectionLost: failure.Failure(error.ConnectionLost())
        }):
        """Utility function for disconnecting a selectable.

        Supports half-close notification, isRead should be boolean indicating
        whether error resulted from doRead().
        """
        self.removeReader(selectable)
        f = faildict.get(why.__class__)
        if f:
            if (isRead and why.__class__ ==  error.ConnectionDone
                and IHalfCloseableDescriptor.providedBy(selectable)):
                selectable.readConnectionLost(f)
            else:
                self.removeWriter(selectable)
                selectable.connectionLost(f)
        else:
            self.removeWriter(selectable)
            selectable.connectionLost(failure.Failure(why))

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
        if platformType == 'posix':
            if usePTY:
                if childFDs is not None:
                    raise ValueError("Using childFDs is not supported with usePTY=True.")
                return process.PTYProcess(self, executable, args, env, path,
                                          processProtocol, uid, gid, usePTY)
            else:
                return process.Process(self, executable, args, env, path,
                                       processProtocol, uid, gid, childFDs)
        elif platformType == "win32":
            if uid is not None or gid is not None:
                raise ValueError("The uid and gid parameters are not supported on Windows.")
            if usePTY:
                raise ValueError("The usePTY parameter is not supported on Windows.")
            if childFDs:
                raise ValueError("Customizing childFDs is not supported on Windows.")

            if win32process:
                from twisted.internet._dumbwin32proc import Process
                return Process(self, processProtocol, executable, args, env, path)
            else:
                raise NotImplementedError, "spawnProcess not available since pywin32 is not installed."
        else:
            raise NotImplementedError, "spawnProcess only available on Windows or POSIX."

    # IReactorUDP

    def listenUDP(self, port, protocol, interface='', maxPacketSize=8192):
        """Connects a given L{DatagramProtocol} to the given numeric UDP port.

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

    def listenMulticast(self, port, protocol, interface='', maxPacketSize=8192, listenMultiple=False):
        """Connects a given DatagramProtocol to the given numeric UDP port.

        EXPERIMENTAL.

        @returns: object conforming to IListeningPort.
        """
        p = udp.MulticastPort(port, protocol, interface, maxPacketSize, self, listenMultiple)
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

    def listenUNIX(self, address, factory, backlog=50, mode=0666, wantPID=0):
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

    def listenTCP(self, port, factory, backlog=50, interface=''):
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

    def listenSSL(self, port, factory, contextFactory, backlog=50, interface=''):
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

    def _removeAll(self, readers, writers):
        """
        Remove all readers and writers, and return list of Selectables.

        Meant for calling from subclasses, to implement removeAll, like::

          def removeAll(self):
              return self._removeAll(reads, writes)

        where C{reads} and C{writes} are iterables.
        """
        readers = [reader for reader in readers if
                   reader is not self.waker]

        readers_dict = {}
        for reader in readers:
            readers_dict[reader] = 1

        for reader in readers:
            self.removeReader(reader)
            self.removeWriter(reader)

        writers = [writer for writer in writers if
                   writer not in readers_dict]
        for writer in writers:
            self.removeWriter(writer)

        return readers+writers


if sslEnabled:
    classImplements(PosixReactorBase, IReactorSSL)
if unixEnabled:
    classImplements(PosixReactorBase, IReactorUNIX, IReactorUNIXDatagram)
if processEnabled:
    classImplements(PosixReactorBase, IReactorProcess)

__all__ = ["PosixReactorBase"]
