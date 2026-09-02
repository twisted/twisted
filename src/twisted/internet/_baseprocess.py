# -*- test-case-name: twisted.test.test_process -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Cross-platform process-related functionality used by different
L{IReactorProcess} implementations.
"""

from twisted.internet.interfaces import IProcessProtocol
from twisted.logger import Logger
from twisted.python.failure import Failure

_log = Logger()


class BaseProcess:
    pid: int | None = None
    status: int | None = None
    lostProcess = 0
    proto: IProcessProtocol | None = None

    def __init__(self, protocol: IProcessProtocol | None) -> None:
        self.proto = protocol

    def _getReason(self, status: int) -> BaseException:
        """
        Convert a process exit status into an exception.
        Subclasses must override this method.

        @param status: The status reported when the child process exits.

        @return: An exception describing how the process terminated.
        """
        raise NotImplementedError("_getReason")

    def _callProcessExited(self, reason: BaseException) -> None:
        if self.proto is not None:
            with _log.failuresHandled("while calling processExited:"):
                self.proto.processExited(Failure(reason))

    def processEnded(self, status: int) -> None:
        """
        This is called when the child terminates.
        """
        self.status = status
        self.lostProcess += 1
        self.pid = None
        self._callProcessExited(self._getReason(status))
        self.maybeCallProcessEnded()

    def maybeCallProcessEnded(self) -> None:
        """
        Call processEnded on protocol after final cleanup.
        """
        if self.proto is not None and self.status is not None:
            reason = self._getReason(self.status)
            proto = self.proto
            self.proto = None
            with _log.failuresHandled("while calling processEnded:"):
                proto.processEnded(Failure(reason))
