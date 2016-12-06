# -*- test-case-name: twisted.application.runner.test.test_pidfile -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
PID file.
"""

import errno
from os import getpid, kill, name as SYSTEM_NAME

from zope.interface import Interface, implementer

from twisted.logger import Logger



class IPIDFile(Interface):
    """
    Manages a file that remembers a process ID.
    """

    def read():
        """
        Read the process ID stored in this PID file.

        @return: The contained process ID.
        @rtype: L{int}

        @raise NoPIDFound: If this PID file does not exist.
        @raise EnvironmentError: If this PID file cannot be read.
        @raise ValueError: If this PID file's content is invalid.
        """


    def writeRunningPID():
        """
        Store the PID of the current process in this PID file.

        @raise EnvironmentError: If this PID file cannot be written.
        """


    def remove():
        """
        Remove this PID file.

        @raise EnvironmentError: If this PID file cannot be removed.
        """


    def isRunning():
        """
        Determine whether there is a running process corresponding to the PID
        in this PID file.

        @return: True if this PID file contains a PID and a process with that
        PID is currently running; false otherwise.
        @rtype: L{bool}

        @raise EnvironmentError: If this PID file cannot be read.
        @raise InvalidPIDFileError: If this PID file's content is invalid.
        @raise StalePIDFileError: If this PID file's content refers to a PID
            for which there is no corresponding running process.
        """


    def __enter__():
        """
        Enter a context using this PIDFile.

        Writes the PID file with the PID of the running process.

        @raise AlreadyRunningError: A process corresponding to the PID in this
            PID file is already running.
        """


    def __exit__(excType, excValue, traceback):
        """
        Exit a context using this PIDFile.

        Removes the PID file.
        """



@implementer(IPIDFile)
class PIDFile(object):
    """
    Concrete implementation of L{IPIDFile} based on C{IFilePath}.
    """

    _log = Logger()


    @staticmethod
    def _format(pid):
        """
        Format a PID file's content.

        @param pid: A process ID.
        @type pid: int

        @return: Formatted PID file contents.
        @rtype: L{bytes}
        """
        return u"{}\n".format(int(pid)).encode("utf-8")


    def __init__(self, filePath):
        """
        @param filePath: The path to the PID file on disk.
        @type filePath: L{IFilePath}
        """
        self.filePath = filePath


    def read(self):
        """
        @see: L{IPIDFile.read}
        """
        pidString = b""
        try:
            with self.filePath.open() as fh:
                for pidString in fh:
                    break
        except OSError as e:
            if e.errno == errno.ENOENT:  # No such file
                raise NoPIDFound("PID file does not exist")
            raise

        try:
            return int(pidString)
        except ValueError:
            raise InvalidPIDFileError(
                "non-integer PID value in PID file: {!r}".format(pidString)
            )


    def _write(self, pid):
        """
        Store a PID in this PID file.

        @param pid: A PID to store.
        @type pid: L{int}

        @raise EnvironmentError: If this PID file cannot be written.
        """
        self.filePath.setContent(self._format(pid=pid))


    def writeRunningPID(self):
        """
        @see: L{IPIDFile.writeRunningPID}
        """
        self._write(getpid())


    def remove(self):
        """
        @see: L{IPIDFile.remove}
        """
        self.filePath.remove()


    def isRunning(self):
        """
        @see: L{IPIDFile.isRunning}
        """
        try:
            pid = self.read()
        except NoPIDFound:
            return False

        if SYSTEM_NAME == "posix":
            return self._pidIsRunningPOSIX(pid)
        else:
            raise NotImplementedError(
                "isRunning is not implemented on {}".format(SYSTEM_NAME)
            )


    @staticmethod
    def _pidIsRunningPOSIX(pid):
        """
        POSIX implementation for running process check.

        Determine whether there is a running process corresponding to the given
        PID.

        @return: True if the given PID is currently running; false otherwise.
        @rtype: L{bool}

        @raise EnvironmentError: If this PID file cannot be read.
        @raise InvalidPIDFileError: If this PID file's content is invalid.
        @raise StalePIDFileError: If this PID file's content refers to a PID
            for which there is no corresponding running process.
        """
        try:
            kill(pid, 0)
        except OSError as e:
            if e.errno == errno.ESRCH:  # No such process
                raise StalePIDFileError(
                    "PID file refers to non-existing process"
                )
            elif e.errno == errno.EPERM:  # Not permitted to kill
                return True
            else:
                raise
        else:
            return True


    def __enter__(self):
        """
        @see: L{IPIDFile.__enter__}
        """
        try:
            if self.isRunning():
                raise AlreadyRunningError()
        except StalePIDFileError:
            self._log.info("Replacing stale PID file: {log_source}")
        self.writeRunningPID()
        return self


    def __exit__(self, excType, excValue, traceback):
        """
        @see: L{IPIDFile.__exit__}
        """
        self.remove()



@implementer(IPIDFile)
class NonePIDFile(object):
    """
    PID file implementation that does nothing.

    This is meant to be used as a "active None" object in place of a PID file
    when no PID file is desired.
    """

    def __init__(self):
        pass


    def read(self):
        """
        @see: L{IPIDFile.read}
        """
        raise NoPIDFound("PID file does not exist")


    def _write(self, pid):
        raise OSError(errno.EPERM, "Operation not permitted")


    def writeRunningPID(self):
        """
        @see: L{IPIDFile.writeRunningPID}
        """
        self._write(0)


    def remove(self):
        """
        @see: L{IPIDFile.remove}
        """
        raise OSError(errno.ENOENT, "No such file or directory")


    def isRunning(self):
        """
        @see: L{IPIDFile.isRunning}
        """
        return False


    def __enter__(self):
        """
        @see: L{IPIDFile.__enter__}
        """
        return self


    def __exit__(self, excType, excValue, traceback):
        """
        @see: L{IPIDFile.__exit__}
        """
        pass



nonePIDFile = NonePIDFile()



class AlreadyRunningError(Exception):
    """
    Process is already running.
    """



class InvalidPIDFileError(Exception):
    """
    PID file contents are invalid.
    """



class StalePIDFileError(Exception):
    """
    PID file contents are valid, but there is no process with the referenced
    PID.
    """



class NoPIDFound(Exception):
    """
    No PID found in PID file.
    """
