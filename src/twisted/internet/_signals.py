# -*- test-case-name: twisted.internet.test.test_sigchld -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module is used to integrate child process termination into a
reactor event loop.  This is a challenging feature to provide because
most platforms indicate process termination via SIGCHLD and do not
provide a way to wait for that signal and arbitrary I/O events at the
same time.  The naive implementation involves installing a Python
SIGCHLD handler; unfortunately this leads to other syscalls being
interrupted (whenever SIGCHLD is received) and failing with EINTR
(which almost no one is prepared to handle).  This interruption can be
disabled via siginterrupt(2) (or one of the equivalent mechanisms);
however, if the SIGCHLD is delivered by the platform to a non-main
thread (not a common occurrence, but difficult to prove impossible),
the main thread (waiting on select() or another event notification
API) may not wake up leading to an arbitrary delay before the child
termination is noticed.

The basic solution to all these issues involves enabling SA_RESTART
(ie, disabling system call interruption) and registering a C signal
handler which writes a byte to a pipe.  The other end of the pipe is
registered with the event loop, allowing it to wake up shortly after
SIGCHLD is received.  See L{twisted.internet.posixbase._SIGCHLDWaker}
for the implementation of the event loop side of this solution.  The
use of a pipe this way is known as the U{self-pipe
trick<http://cr.yp.to/docs/selfpipe.html>}.

From Python version 2.6, C{signal.siginterrupt} and C{signal.set_wakeup_fd}
provide the necessary C signal handler which writes to the pipe to be
registered with C{SA_RESTART}.
"""

from __future__ import annotations

from zope.interface import Attribute, Interface, implementer

import contextlib
import os
import socket


from twisted.python import failure
from . import _signals, fdesc



import signal
from types import FrameType
from typing import Callable, Optional

from typing_extensions import TypeAlias

from twisted.python.runtime import platformType

SignalHandler: TypeAlias = Callable[[int, Optional[FrameType]], None]


def installHandler(fd):
    """
    Install a signal handler which will write a byte to C{fd} when
    I{SIGCHLD} is received.

    This is implemented by installing a SIGCHLD handler that does nothing,
    setting the I{SIGCHLD} handler as not allowed to interrupt system calls,
    and using L{signal.set_wakeup_fd} to do the actual writing.

    @param fd: The file descriptor to which to write when I{SIGCHLD} is
        received.
    @type fd: C{int}
    """
    if fd == -1:
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    else:

        def noopSignalHandler(*args):
            pass

        signal.signal(signal.SIGCHLD, noopSignalHandler)
        signal.siginterrupt(signal.SIGCHLD, False)
    return signal.set_wakeup_fd(fd)


def isDefaultHandler():
    """
    Determine whether the I{SIGCHLD} handler is the default or not.
    """
    return signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL


from typing import Protocol


class SignalHandling(Protocol):
    """
    The L{SignalHandling} protocol enables customizable signal-handling
    behaviors for reactors.

    A value that confirms to L{SignalHandling} has install and uninstall hooks
    that are called by a reactor at the correct times to have the (typically)
    process-global effects necessary for dealing with signals.
    """

    def install(self) -> None:
        """
        Install the signal handlers.
        """

    def uninstall(self) -> None:
        """
        Restore signal handlers to their original state.
        """


from attrs import define, frozen


@frozen
class _WithoutSignalHandling:
    """
    A L{SignalHandling} implementation that does no signal handling.

    This is the implementation of C{installSignalHandlers=False}.
    """

    def install(self) -> None:
        """
        Do not install any signal handlers.
        """

    def uninstall(self) -> None:
        """
        Do nothing because L{install} installed nothing.
        """


from twisted.python import log


@frozen
class _WithSignalHandling:
    """
    A reactor core helper that can manage signals: it installs signal handlers
    at start time.
    """

    _sigInt: SignalHandler
    _sigBreak: SignalHandler
    _sigTerm: SignalHandler

    def install(self) -> None:
        """
        Install the signal handlers for the Twisted event loop.
        """
        try:
            import signal
        except ImportError:
            log.msg(
                "Warning: signal module unavailable -- "
                "not installing signal handlers."
            )
            return

        if signal.getsignal(signal.SIGINT) == signal.default_int_handler:
            # only handle if there isn't already a handler, e.g. for Pdb.
            signal.signal(signal.SIGINT, self._sigInt)
        signal.signal(signal.SIGTERM, self._sigTerm)

        # Catch Ctrl-Break in windows
        SIGBREAK = getattr(signal, "SIGBREAK", None)
        if SIGBREAK is not None:
            signal.signal(SIGBREAK, self._sigBreak)

    def uninstall(self) -> None:
        """
        Do nothing for historical reasons.
        """
        # TODO Make this do something, someday, because cleaning up your state
        # is a nice idea.


from twisted.internet.interfaces import IReadDescriptor


@define
class _WithChildSignalHandling:
    """
    @ivar _childWaker: L{None} or a reference to the L{_SIGCHLDWaker}
        which is used to properly notice child process termination.
    """

    _signals: SignalHandling
    _addInternalReader: Callable[[IReadDescriptor], object]
    _childWaker: Optional[_SIGCHLDWaker] = None

    def uninstall(self):
        """
        If a child waker was created and installed, uninstall it now.

        Since this disables reactor functionality and is only called when the
        reactor is stopping, it doesn't provide any directly useful
        functionality, but the cleanup of reactor-related process-global state
        that it does helps in unit tests involving multiple reactors and is
        generally just a nice thing.
        """
        self._signals.uninstallHandler()  # XXX this is untested
        # XXX This would probably be an alright place to put all of the
        # cleanup code for all internal readers (here and in the base class,
        # anyway).  See #3063 for that cleanup task.
        if self._childWaker is not None:
            self._childWaker.uninstall()

    def install(self) -> None:
        """
        Extend the basic signal handling logic to also support
        handling SIGCHLD to know when to try to reap child processes.
        """
        self._signals.install()  # XXX is this untested?

        if self._childWaker is None:
            self._childWaker = _SIGCHLDWaker(self)
            self._addInternalReader(self._childWaker)

        self._childWaker.install()
        # Also reap all processes right now, in case we missed any
        # signals before we installed the SIGCHLD waker/handler.
        # This should only happen if someone used spawnProcess
        # before calling reactor.run (and the process also exited
        # already).
        process.reapAllProcesses()


from . import process


@implementer(IReadDescriptor)
class _FDWaker(log.Logger):
    """
    The I{self-pipe trick<http://cr.yp.to/docs/selfpipe.html>}, used to wake
    up the main loop from another thread or a signal handler.

    L{_FDWaker} is a base class for waker implementations based on
    writing to a pipe being monitored by the reactor.

    @ivar o: The file descriptor for the end of the pipe which can be
        written to wake up a reactor monitoring this waker.

    @ivar i: The file descriptor which should be monitored in order to
        be awoken by this waker.
    """

    disconnected = 0

    i = None
    o = None

    def __init__(self, reactor):
        """Initialize."""
        self.reactor = reactor
        self.i, self.o = os.pipe()
        fdesc.setNonBlocking(self.i)
        fdesc._setCloseOnExec(self.i)
        fdesc.setNonBlocking(self.o)
        fdesc._setCloseOnExec(self.o)
        self.fileno = lambda: self.i

    def doRead(self):
        """
        Read some bytes from the pipe and discard them.
        """
        fdesc.readFromFD(self.fileno(), lambda data: None)

    def connectionLost(self, reason):
        """Close both ends of my pipe."""
        if not hasattr(self, "o"):
            return
        for fd in self.i, self.o:
            try:
                os.close(fd)
            except OSError:
                pass
        del self.i, self.o


class _SIGCHLDWaker(_FDWaker):
    """
    L{_SIGCHLDWaker} can wake up a reactor whenever C{SIGCHLD} is
    received.

    @see: L{twisted.internet._signals}
    """

    def install(self):
        """
        Install the handler necessary to make this waker active.
        """
        _signals.installHandler(self.o)

    def uninstall(self):
        """
        Remove the handler which makes this waker active.
        """
        _signals.installHandler(-1)

    def doRead(self):
        """
        Having woken up the reactor in response to receipt of
        C{SIGCHLD}, reap the process which exited.

        This is called whenever the reactor notices the waker pipe is
        writeable, which happens soon after any call to the C{wakeUp}
        method.
        """
        _FDWaker.doRead(self)
        process.reapAllProcesses()


class _IWaker(Interface):
    """
    Interface to wake up the event loop based on the self-pipe trick.

    The U{I{self-pipe trick}<http://cr.yp.to/docs/selfpipe.html>}, used to wake
    up the main loop from another thread or a signal handler.
    This is why we have wakeUp together with doRead

    This is used by threads or signals to wake up the event loop.
    """

    disconnected = Attribute("")

    def wakeUp():
        """
        Called when the event should be wake up.
        """

    def doRead():
        """
        Read some data from my connection and discard it.
        """

    def connectionLost(reason: failure.Failure):
        """
        Called when connection was closed and the pipes.
        """


import errno

from twisted.python import util


@implementer(_IWaker)
class _SocketWaker(log.Logger):
    """
    The I{self-pipe trick<http://cr.yp.to/docs/selfpipe.html>}, implemented
    using a pair of sockets rather than pipes (due to the lack of support in
    select() on Windows for pipes), used to wake up the main loop from
    another thread.
    """

    disconnected = 0

    def __init__(self, reactor):
        """Initialize."""
        self.reactor = reactor
        # Following select_trigger (from asyncore)'s example;
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with contextlib.closing(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            client.connect(server.getsockname())
            reader, clientaddr = server.accept()
        client.setblocking(0)
        reader.setblocking(0)
        self.r = reader
        self.w = client
        self.fileno = self.r.fileno

    def wakeUp(self):
        """Send a byte to my connection."""
        try:
            util.untilConcludes(self.w.send, b"x")
        except OSError as e:
            if e.args[0] != errno.WSAEWOULDBLOCK:
                raise

    def doRead(self):
        """
        Read some data from my connection.
        """
        try:
            self.r.recv(8192)
        except OSError:
            pass

    def connectionLost(self, reason):
        self.r.close()
        self.w.close()


@implementer(_IWaker)
class _UnixWaker(_FDWaker):
    """
    This class provides a simple interface to wake up the event loop.

    This is used by threads or signals to wake up the event loop.
    """

    def wakeUp(self):
        """Write one byte to the pipe, and flush it."""
        # We don't use fdesc.writeToFD since we need to distinguish
        # between EINTR (try again) and EAGAIN (do nothing).
        if self.o is not None:
            try:
                util.untilConcludes(os.write, self.o, b"x")
            except OSError as e:
                # XXX There is no unit test for raising the exception
                # for other errnos. See #4285.
                if e.errno != errno.EAGAIN:
                    raise


if platformType == "posix":
    Waker = _UnixWaker
else:
    # Primarily Windows and Jython.
    Waker = _SocketWaker  # type: ignore[misc,assignment]
