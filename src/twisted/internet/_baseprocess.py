# -*- test-case-name: twisted.test.test_process -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Cross-platform process-related functionality used by different
L{IReactorProcess} implementations.
"""

from twisted.logger import Logger
from twisted.python.failure import Failure

_log = Logger()


class BaseProcess:
    pid: int | None = None
    status: int | None = None
    lostProcess = 0
    proto = None

    def __init__(self, protocol):
        self.proto = protocol

    def _callProcessExited(self, reason):
        with _log.failuresHandled("while calling processExited:"):
            self.proto.processExited(Failure(reason))

    def processEnded(self, status):
        """
        This is called when the child terminates.
        """
        self.status = status
        self.lostProcess += 1
        self.pid = None
        self._callProcessExited(self._getReason(status))
        self.maybeCallProcessEnded()

    def maybeCallProcessEnded(self):
        """
        Call processEnded on protocol after final cleanup.
        """
        if self.proto is not None:
            reason = self._getReason(self.status)
            proto = self.proto
            self.proto = None
            with _log.failuresHandled("while calling processEnded:"):
                proto.processEnded(Failure(reason))
