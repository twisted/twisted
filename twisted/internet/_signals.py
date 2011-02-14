# -*- test-case-name: twisted.test.test_process,twisted.internet.test.test_process -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module provides a uniform interface to the several mechanisms which are
possibly available for dealing with signals.

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

The actual solution implemented in this module depends on the version
of Python.  From version 2.6, C{signal.siginterrupt} and
C{signal.set_wakeup_fd} allow the necessary C signal handler which
writes to the pipe to be registered with C{SA_RESTART}.  Prior to 2.6,
the L{twisted.internet._sigchld} extension module provides similar
functionality.

If neither of these is available, a Python signal handler is used
instead.  This is essentially the naive solution mentioned above and
has the problems described there.
"""

import os

try:
    from signal import set_wakeup_fd, siginterrupt
except ImportError:
    set_wakeup_fd = siginterrupt = None

try:
    import signal
except ImportError:
    signal = None

from twisted.python.log import msg

try:
    from twisted.internet._sigchld import installHandler as _extInstallHandler, \
        isDefaultHandler as _extIsDefaultHandler
except ImportError:
    _extInstallHandler = _extIsDefaultHandler = None


class _Handler(object):
    """
    L{_Handler} is a signal handler which writes a byte to a file descriptor
    whenever it is invoked.

    @ivar fd: The file descriptor to which to write.  If this is C{None},
        nothing will be written.
    """
    def __init__(self, fd):
        self.fd = fd


    def __call__(self, *args):
        """
        L{_Handler.__call__} is the signal handler.  It will write a byte to
        the wrapped file descriptor, if there is one.
        """
        if self.fd is not None:
            try:
                os.write(self.fd, '\0')
            except:
                pass



def _installHandlerUsingSignal(fd):
    """
    Install a signal handler which will write a byte to C{fd} when
    I{SIGCHLD} is received.

    This is implemented by creating an instance of L{_Handler} with C{fd}
    and installing it as the signal handler.

    @param fd: The file descriptor to which to write when I{SIGCHLD} is
        received.
    @type fd: C{int}
    """
    if fd == -1:
        previous = signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    else:
        previous = signal.signal(signal.SIGCHLD, _Handler(fd))
    if isinstance(previous, _Handler):
        return previous.fd
    return -1



def _installHandlerUsingSetWakeup(fd):
    """
    Install a signal handler which will write a byte to C{fd} when
    I{SIGCHLD} is received.

    This is implemented by installing an instance of L{_Handler} wrapped
    around C{None}, setting the I{SIGCHLD} handler as not allowed to
    interrupt system calls, and using L{signal.set_wakeup_fd} to do the
    actual writing.

    @param fd: The file descriptor to which to write when I{SIGCHLD} is
        received.
    @type fd: C{int}
    """
    if fd == -1:
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    else:
        signal.signal(signal.SIGCHLD, _Handler(None))
        siginterrupt(signal.SIGCHLD, False)
    return set_wakeup_fd(fd)



def _isDefaultHandler():
    """
    Determine whether the I{SIGCHLD} handler is the default or not.
    """
    return signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL



def _cannotInstallHandler(fd):
    """
    Fail to install a signal handler for I{SIGCHLD}.

    This implementation is used when the supporting code for the other
    implementations is unavailable (on Python versions 2.5 and older where
    neither the L{twisted.internet._sigchld} extension nor the standard
    L{signal} module is available).

    @param fd: Ignored; only for compatibility with the other
        implementations of this interface.

    @raise RuntimeError: Always raised to indicate no I{SIGCHLD} handler can
        be installed.
    """
    raise RuntimeError("Cannot install a SIGCHLD handler")



def _cannotDetermineDefault():
    raise RuntimeError("No usable signal API available")



if set_wakeup_fd is not None:
    msg('using set_wakeup_fd')
    installHandler = _installHandlerUsingSetWakeup
    isDefaultHandler = _isDefaultHandler
elif _extInstallHandler is not None:
    msg('using _sigchld')
    installHandler = _extInstallHandler
    isDefaultHandler = _extIsDefaultHandler
elif signal is not None:
    msg('using signal module')
    installHandler = _installHandlerUsingSignal
    isDefaultHandler = _isDefaultHandler
else:
    msg('nothing unavailable')
    installHandler = _cannotInstallHandler
    isDefaultHandler = _cannotDetermineDefault

