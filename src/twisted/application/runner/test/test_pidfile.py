# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.runner._pidfile}.
"""

from os import getpid

from ...runner import _pidfile
from .._pidfile import PIDFile
from .test_runner import DummyKill, DummyFilePath

import twisted.trial.unittest



class PIDFileTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{PIDFile}.
    """

    def setUp(self):
        # Patch exit and kill so we can capture usage and prevent actual exits
        # and kills.

        # self.exit = DummyExit()
        # self.kill = DummyKill()

        # self.patch(_pidfile, "exit", self.exit)
        # self.patch(_pidfile, "kill", self.kill)

        # Patch getpid so we get a known result

        # self.pid = 1337
        # self.pidFileContent = u"{}\n".format(self.pid).encode("utf-8")
        pass



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


    def test_isRunningTrue(self):
        """
        L{PIDFile.isRunning} returns true for this process.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write()

        self.assertTrue(pidFile.isRunning())
