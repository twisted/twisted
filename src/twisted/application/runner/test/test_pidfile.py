# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.runner._pidfile}.
"""

from os import getpid

from .._pidfile import PIDFile
from .test_runner import DummyFilePath

import twisted.trial.unittest



class PIDFileTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{PIDFile}.
    """

    def test_readWithPID(self):
        """
        L{PIDFile.read} returns the PID from the given file path.
        """
        pid = 1337
        pidFileContent = u"{}\n".format(pid).encode("utf-8")

        pidFile = PIDFile(DummyFilePath(pidFileContent))

        self.assertEqual(pid, pidFile.read())


    def test_readWithoutPID(self):
        """
        L{PIDFile.read} raises ValueError when given an empty file path.
        """
        pidFile = PIDFile(DummyFilePath(b""))

        self.assertRaises(ValueError, pidFile.read)


    def test_readWithBogusPID(self):
        """
        L{PIDFile.read} raises ValueError when given an invalid file path.
        """
        pidFile = PIDFile(DummyFilePath(b"not a pid"))

        self.assertRaises(ValueError, pidFile.read)


    def test_writeDefault(self):
        """
        L{PIDFile.write} with no C{pid} argument stores the PID for the current
            process.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write()

        self.assertEqual(pidFile.read(), getpid())


    def test_writePID(self):
        """
        L{PIDFile.write} stores the given PID.
        """
        pid = 1995

        pidFile = PIDFile(DummyFilePath())
        pidFile.write(pid)

        self.assertEqual(pidFile.read(), pid)


    def test_writePIDInvalid(self):
        """
        L{PIDFile.write} raises ValueError when given an invalid PID.
        """
        pidFile = PIDFile(DummyFilePath())

        self.assertRaises(ValueError, pidFile.write, u"burp")


    def test_remove(self):
        """
        L{PIDFile.remove} removes the PID file.
        """
        pidFile = PIDFile(DummyFilePath(b""))
        self.assertTrue(pidFile.filePath.exists())

        pidFile.remove()
        self.assertFalse(pidFile.filePath.exists())


    def test_isRunningThis(self):
        """
        L{PIDFile.isRunning} returns true for this process (which is running).
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write()

        self.assertTrue(pidFile.isRunning())


    def test_isRunningNotAllowed(self):
        """
        L{PIDFile.isRunning} returns true for a process that we are not allowed
        to kill.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write(1)  # We should not be allowed to kill init, yo.

        self.assertTrue(pidFile.isRunning())


    def test_contextManager(self):
        """
        When used as a context manager, a L{PIDFile} will store the current pid
        on entry, then removes the PID file on exit.
        """
        pidFile = PIDFile(DummyFilePath())
        self.assertFalse(pidFile.filePath.exists())

        with pidFile:
            self.assertTrue(pidFile.filePath.exists())
            self.assertEqual(pidFile.read(), getpid())

        self.assertFalse(pidFile.filePath.exists())
