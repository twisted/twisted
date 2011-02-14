# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._sigchld}, an alternate, superior SIGCHLD
monitoring API.
"""

import os, signal, errno

from twisted.python.log import msg
from twisted.trial.unittest import TestCase
from twisted.internet.fdesc import setNonBlocking
from twisted.internet._signals import installHandler, isDefaultHandler
from twisted.internet._signals import _extInstallHandler, _extIsDefaultHandler
from twisted.internet._signals import _installHandlerUsingSetWakeup, \
    _installHandlerUsingSignal, _isDefaultHandler


class SIGCHLDTestsMixin:
    """
    Mixin for L{TestCase} subclasses which defines several tests for
    I{installHandler} and I{isDefaultHandler}.  Subclasses are expected to
    define C{self.installHandler} and C{self.isDefaultHandler} to invoke the
    implementation to be tested.
    """

    if getattr(signal, 'SIGCHLD', None) is None:
        skip = "Platform does not have SIGCHLD"

    def installHandler(self, fd):
        """
        Override in a subclass to install a SIGCHLD handler which writes a byte
        to the given file descriptor.  Return the previously registered file
        descriptor.
        """
        raise NotImplementedError()


    def isDefaultHandler(self):
        """
        Override in a subclass to determine if the current SIGCHLD handler is
        SIG_DFL or not.  Return True if it is SIG_DFL, False otherwise.
        """
        raise NotImplementedError()


    def pipe(self):
        """
        Create a non-blocking pipe which will be closed after the currently
        running test.
        """
        read, write = os.pipe()
        self.addCleanup(os.close, read)
        self.addCleanup(os.close, write)
        setNonBlocking(read)
        setNonBlocking(write)
        return read, write


    def setUp(self):
        """
        Save the current SIGCHLD handler as reported by L{signal.signal} and
        the current file descriptor registered with L{installHandler}.
        """
        handler = signal.getsignal(signal.SIGCHLD)
        if handler != signal.SIG_DFL:
            self.signalModuleHandler = handler
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        else:
            self.signalModuleHandler = None

        self.oldFD = self.installHandler(-1)

        if self.signalModuleHandler is not None and self.oldFD != -1:
            msg("SIGCHLD setup issue: %r %r" % (self.signalModuleHandler, self.oldFD))
            raise RuntimeError("You used some signal APIs wrong!  Try again.")


    def tearDown(self):
        """
        Restore whatever signal handler was present when setUp ran.
        """
        # If tests set up any kind of handlers, clear them out.
        self.installHandler(-1)
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)

        # Now restore whatever the setup was before the test ran.
        if self.signalModuleHandler is not None:
            signal.signal(signal.SIGCHLD, self.signalModuleHandler)
        elif self.oldFD != -1:
            self.installHandler(self.oldFD)


    def test_isDefaultHandler(self):
        """
        L{isDefaultHandler} returns true if the SIGCHLD handler is SIG_DFL,
        false otherwise.
        """
        self.assertTrue(self.isDefaultHandler())
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        self.assertFalse(self.isDefaultHandler())
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        self.assertTrue(self.isDefaultHandler())
        signal.signal(signal.SIGCHLD, lambda *args: None)
        self.assertFalse(self.isDefaultHandler())


    def test_returnOldFD(self):
        """
        L{installHandler} returns the previously registered file descriptor.
        """
        read, write = self.pipe()
        oldFD = self.installHandler(write)
        self.assertEqual(self.installHandler(oldFD), write)


    def test_uninstallHandler(self):
        """
        C{installHandler(-1)} removes the SIGCHLD handler completely.
        """
        read, write = self.pipe()
        self.assertTrue(self.isDefaultHandler())
        self.installHandler(write)
        self.assertFalse(self.isDefaultHandler())
        self.installHandler(-1)
        self.assertTrue(self.isDefaultHandler())


    def test_installHandler(self):
        """
        The file descriptor passed to L{installHandler} has a byte written to
        it when SIGCHLD is delivered to the process.
        """
        read, write = self.pipe()
        self.installHandler(write)

        exc = self.assertRaises(OSError, os.read, read, 1)
        self.assertEqual(exc.errno, errno.EAGAIN)

        os.kill(os.getpid(), signal.SIGCHLD)

        self.assertEqual(len(os.read(read, 5)), 1)



class DefaultSIGCHLDTests(SIGCHLDTestsMixin, TestCase):
    """
    Tests for whatever implementation is selected for the L{installHandler}
    and L{isDefaultHandler} APIs.
    """
    installHandler = staticmethod(installHandler)
    isDefaultHandler = staticmethod(isDefaultHandler)



class ExtensionSIGCHLDTests(SIGCHLDTestsMixin, TestCase):
    """
    Tests for the L{twisted.internet._sigchld} implementation of the
    L{installHandler} and L{isDefaultHandler} APIs.
    """
    try:
        import twisted.internet._sigchld
    except ImportError:
        skip = "twisted.internet._sigchld is not available"

    installHandler = _extInstallHandler
    isDefaultHandler = _extIsDefaultHandler



class SetWakeupSIGCHLDTests(SIGCHLDTestsMixin, TestCase):
    """
    Tests for the L{signal.set_wakeup_fd} implementation of the
    L{installHandler} and L{isDefaultHandler} APIs.
    """
    # Check both of these.  On Ubuntu 9.10 (to take an example completely at
    # random), Python 2.5 has set_wakeup_fd but not siginterrupt.
    if (getattr(signal, 'set_wakeup_fd', None) is None
        or getattr(signal, 'siginterrupt', None) is None):
        skip = "signal.set_wakeup_fd is not available"

    installHandler = staticmethod(_installHandlerUsingSetWakeup)
    isDefaultHandler = staticmethod(_isDefaultHandler)



class PlainSignalModuleSIGCHLDTests(SIGCHLDTestsMixin, TestCase):
    """
    Tests for the L{signal.signal} implementation of the L{installHandler}
    and L{isDefaultHandler} APIs.
    """
    installHandler = staticmethod(_installHandlerUsingSignal)
    isDefaultHandler = staticmethod(_isDefaultHandler)
