# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.runner._pidfile}.
"""

import errno
from os import getpid, name as SYSTEM_NAME
from io import BytesIO

from twisted.python.filepath import FilePath

from ...runner import _pidfile
from .._pidfile import (
    PIDFile, AlreadyRunningError, InvalidPIDFileError, StalePIDFileError,
    NonePIDFile, NoPIDFound,
)

import twisted.trial.unittest
from twisted.trial.unittest import SkipTest



class PIDFileTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{PIDFile}.
    """

    def test_formatWithPID(self):
        """
        L{PIDFile.format} returns the expected format when given a PID.
        """
        self.assertEqual(PIDFile.format(pid=1337), b"1337\n")


    def test_readWithPID(self):
        """
        L{PIDFile.read} returns the PID from the given file path.
        """
        pid = 1337

        pidFile = PIDFile(DummyFilePath(PIDFile.format(pid=pid)))

        self.assertEqual(pid, pidFile.read())


    def test_readWithoutPID(self):
        """
        L{PIDFile.read} raises L{InvalidPIDFileError} when given an empty file
        path.
        """
        pidFile = PIDFile(DummyFilePath(b""))

        self.assertRaises(InvalidPIDFileError, pidFile.read)


    def test_readWithBogusPID(self):
        """
        L{PIDFile.read} raises L{NoPIDFound} when given a non-existing file
        path.
        """
        pidFile = PIDFile(DummyFilePath())

        self.assertRaises(NoPIDFound, pidFile.read)


    def test_readDoesntExist(self):
        """
        L{PIDFile.read} raises the PID from the given file path.
        """
        pid = 1337

        pidFile = PIDFile(DummyFilePath(PIDFile.format(pid=pid)))

        self.assertEqual(pid, pidFile.read())


    def test_readOpenRaisesOSErrorNotENOENT(self):
        """
        L{PIDFile.read} re-raises L{OSError} if the associated C{errno} is
        anything other than L{errno.ENOENT}.
        """
        def oops(mode="r"):
            raise OSError(errno.EIO, "I/O error")

        self.patch(DummyFilePath, "open", oops)

        pidFile = PIDFile(DummyFilePath())

        error = self.assertRaises(OSError, pidFile.read)
        self.assertEqual(error.errno, errno.EIO)


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
        L{PIDFile.write} raises L{ValueError} when given an invalid PID.
        """
        pidFile = PIDFile(DummyFilePath())

        self.assertRaises(ValueError, pidFile.write, u"burp")


    def test_writeRunningPID(self):
        """
        L{PIDFile.writeRunningPID} stores the PID for the current process.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.writeRunningPID()

        self.assertEqual(pidFile.read(), getpid())


    def test_remove(self):
        """
        L{PIDFile.remove} removes the PID file.
        """
        pidFile = PIDFile(DummyFilePath(b""))
        self.assertTrue(pidFile.filePath.exists())

        pidFile.remove()
        self.assertFalse(pidFile.filePath.exists())


    def test_isRunningDoesExist(self):
        """
        L{PIDFile.isRunning} returns true for a process that does exist.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write(1337)

        def kill(pid, signal):
            return  # Don't actually kill anything

        self.patch(_pidfile, "kill", kill)

        self.assertTrue(pidFile.isRunning())


    def test_isRunningThis(self):
        """
        L{PIDFile.isRunning} returns true for this process (which is running).

        @note: This differs from L{PIDFileTests.test_isRunningDoesExist} in
        that it actually invokes the C{kill} system call, which is useful for
        testing of our chosen method for probing the existence of a process.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.writeRunningPID()

        self.assertTrue(pidFile.isRunning())


    def test_isRunningDoesNotExist(self):
        """
        L{PIDFile.isRunning} raises L{StalePIDFileError} for a process that
        does not exist (errno=ESRCH).
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write(1337)

        def kill(pid, signal):
            raise OSError(errno.ESRCH, "No such process")

        self.patch(_pidfile, "kill", kill)

        self.assertRaises(StalePIDFileError, pidFile.isRunning)


    def test_isRunningNotAllowed(self):
        """
        L{PIDFile.isRunning} returns true for a process that we are not allowed
        to kill (errno=EPERM).
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write(1337)

        def kill(pid, signal):
            raise OSError(errno.EPERM, "Operation not permitted")

        self.patch(_pidfile, "kill", kill)

        self.assertTrue(pidFile.isRunning())


    def test_isRunningInit(self):
        """
        L{PIDFile.isRunning} returns true for a process that we are not allowed
        to kill (errno=EPERM).

        @note: This differs from L{PIDFileTests.test_isRunningNotAllowed} in
        that it actually invokes the C{kill} system call, which is useful for
        testing of our chosen method for probing the existence of a process
        that we are not allowed to kill.

        @note: In this case, we try killing C{init}, which is process #1 on
        POSIX systems, so this test is not portable.  C{init} should always be
        running and should not be killable by non-root users.
        """
        if SYSTEM_NAME != "posix":
            raise SkipTest("This test assumes POSIX")

        pidFile = PIDFile(DummyFilePath())
        pidFile.write(1)  # PID 1 is init on POSIX systems

        self.assertTrue(pidFile.isRunning())


    def test_isRunningUnknownErrno(self):
        """
        L{PIDFile.isRunning} re-raises L{OSError} if the attached C{errno}
        value from L{os.kill} is not an expected one.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.writeRunningPID()

        def kill(pid, signal):
            raise OSError(errno.EEXIST, "File exists")

        self.patch(_pidfile, "kill", kill)

        self.assertRaises(OSError, pidFile.isRunning)


    def test_isRunningNoPIDFile(self):
        """
        L{PIDFile.isRunning} returns false if the PID file doesn't exist.
        """
        pidFile = PIDFile(DummyFilePath())

        self.assertFalse(pidFile.isRunning())


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


    def test_contextManagerDoesntExist(self):
        """
        When used as a context manager, a L{PIDFile} will replace the
        underlying PIDFile rather than raising L{AlreadyRunningError} if the
        contained PID file exists but refers to a non-running PID.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write(1337)

        def kill(pid, signal):
            raise OSError(errno.ESRCH, "No such process")

        self.patch(_pidfile, "kill", kill)

        self.assertRaises(StalePIDFileError, pidFile.isRunning)

        with pidFile:
            self.assertEqual(pidFile.read(), getpid())


    def test_contextManagerAlreadyRunning(self):
        """
        When used as a context manager, a L{PIDFile} will raise
        L{AlreadyRunningError} if the there is already a running process with
        the contained PID.
        """
        pidFile = PIDFile(DummyFilePath())
        pidFile.write(1337)

        def kill(pid, signal):
            return  # Don't actually kill anything

        self.patch(_pidfile, "kill", kill)

        self.assertTrue(pidFile.isRunning())

        def useContext():
            with pidFile:
                pass

        self.assertRaises(AlreadyRunningError, useContext)



class NonePIDFileTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{NonePIDFile}.
    """

    def test_read(self):
        """
        L{NonePIDFile.read} raises L{NoPIDFound}.
        """
        pidFile = NonePIDFile()

        self.assertRaises(NoPIDFound, pidFile.read)


    def test_write(self):
        """
        L{NonePIDFile.write} raises L{OSError} with an errno of L{errno.EPERM}.
        """
        pidFile = NonePIDFile()

        error = self.assertRaises(OSError, pidFile.write)
        self.assertEqual(error.errno, errno.EPERM)


    def test_remove(self):
        """
        L{NonePIDFile.remove} raises L{OSError} with an errno of L{errno.EPERM}.
        """
        pidFile = NonePIDFile()

        error = self.assertRaises(OSError, pidFile.remove)
        self.assertEqual(error.errno, errno.ENOENT)


    def test_isRunning(self):
        """
        L{NonePIDFile.isRunning} returns L{False}.
        """
        pidFile = NonePIDFile()

        self.assertEqual(pidFile.isRunning(), False)


    def test_contextManager(self):
        """
        When used as a context manager, a L{NonePIDFile} doesn't raise, despite
        not existing.
        """
        pidFile = NonePIDFile()

        with pidFile:
            pass



class DummyFilePath(FilePath):
    """
    Stub for L{twisted.python.filepath.FilePath} which returns a stream
    containing the given data when opened.
    """

    def __init__(self, content=None):
        self.setContent(content)


    def open(self, mode="r"):
        if not self._exists:
            raise OSError(errno.ENOENT, "No such file or directory")
        return BytesIO(self._content)


    def setContent(self, content):
        self._exists = content is not None
        self._content = content


    def getContent(self):
        return self._content


    def remove(self):
        self.setContent(None)


    def exists(self):
        return self._exists
