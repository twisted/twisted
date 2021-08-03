# -*- test-case-name: twisted.trial._dist.test.test_workertrial -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of C{AMP} worker commands, and main executable entry point for
the workers.

This is the code executed in the remote sub-process.

@since: 12.3
"""

import sys
import os
import errno
from io import StringIO
from typing import Callable


def _setupPath(environ):
    """
    Override C{sys.path} with what the parent passed in B{TRIAL_PYTHONPATH}.

    @see: twisted.trial._dist.disttrial.DistTrialRunner.launchWorkerProcesses
    """
    if "TRIAL_PYTHONPATH" in environ:
        sys.path[:] = environ["TRIAL_PYTHONPATH"].split(os.pathsep)


_setupPath(os.environ)


from twisted.internet.protocol import FileWrapper
from twisted.python.log import startLoggingWithObserver, textFromEventDict
from twisted.trial._dist.options import WorkerOptions
from twisted.trial._dist import managercommands, _WORKER_AMP_STDIN, _WORKER_AMP_STDOUT
from twisted.trial._dist.worker import WorkerProtocol


class WorkerLogObserver:
    """
    A log observer that forward its output to a C{AMP} protocol.
    """

    def __init__(self, protocol: WorkerProtocol):
        """
        @param protocol: a connected C{AMP} protocol instance.
        """
        self.protocol = protocol

    def emit(self, eventDict):
        """
        Produce a log output.
        """
        text = textFromEventDict(eventDict)
        if text is None:
            return
        self.protocol.callRemote(managercommands.TestWrite, out=text)


class WorkerStdout(StringIO):
    """
    Handles forwarding of the sub-process sys.stdout to the central
    disttrial process via the AMP protocol.
    """

    # Always use UTF-8 as this is the encoding used over our AMP.
    encoding = "utf-8"

    def __init__(self, protocol: WorkerProtocol):
        """
        @param protocol: a connected C{AMP} protocol instance.
        """
        super().__init__()
        self._protocol = protocol

    def write(self, s: str) -> int:
        """
        @param s: The string to be forwarded.

        @return: Always returns the length of C{s}, being optimistic that the
          delivery to remote process is successful.
          This is async API the low-level data delivery is done async.
        """
        if not isinstance(s, str):
            raise TypeError(f"string argument expected, got {type(str)}")

        # Just forward the data without any proceesing as at the AMP
        # protocol `out` is defined as Unicode and AMP will handle the
        # UTF-8 encoding.
        self._protocol.callRemote(managercommands.TestWrite, out=s)
        return len(s)


def main(_fdopen: Callable = os.fdopen, _captureSysStdout: bool = False) -> None:
    """
    Main function to be run if __name__ == "__main__".

    This is called in the sub-process spawned by L{DistTrialRunner}.

    @param _fdopen: If specified, the function to use in place of C{os.fdopen}.

    @param _captureSysStdout: When C{True}, it will replace the standard output
      with an implementation that forward the stream to the distrial control process.
      here to make sure we don't accidentally mess with C{sys.stdout} during testing.
    """
    if _fdopen == os.fdopen:
        # Prepare the subprocess communication pipes as soon as possible,
        # But not when the test is executed under tests.
        #
        # At the low level move AMP pipes from stdout/stdin file descriptors
        # to new file descriptions so that normal code will not read/write from
        # AMP when wanting to communicate with the standard pipes.
        # Restore new stdin/stdout pipes hat are not connected to AMP.
        os.dup2(0, _WORKER_AMP_STDIN, inheritable=False)
        os.dup2(1, _WORKER_AMP_STDOUT, inheritable=False)
        # FIXME: https://twistedmatrix.com/trac/ticket/10156
        # For now the new pipes are not connected to AMP.
        # In a separate ticket we need to add support for stdin/stdout communication
        # over AMP.
        in_file, out_file = os.pipe()
        os.dup2(in_file, 0, inheritable=True)
        os.dup2(out_file, 1, inheritable=True)

    config = WorkerOptions()
    config.parseOptions()

    workerProtocol = WorkerProtocol(config["force-gc"])

    protocolIn = _fdopen(_WORKER_AMP_STDIN, "rb")
    protocolOut = _fdopen(_WORKER_AMP_STDOUT, "wb")
    workerProtocol.makeConnection(FileWrapper(protocolOut))

    observer = WorkerLogObserver(workerProtocol)
    startLoggingWithObserver(observer.emit, False)

    if _captureSysStdout:
        # Only replace high-level streams when not running under unit-tests.
        #
        # Redirect the sys.stdout generate by the worker to the
        # centralized log file.
        sys.stdout = WorkerStdout(workerProtocol)

    while True:
        try:
            r = protocolIn.read(1)
        except OSError as e:
            if e.args[0] == errno.EINTR:
                continue
            else:
                raise
        if r == b"":
            break
        else:
            workerProtocol.dataReceived(r)
            protocolOut.flush()
            sys.stdout.flush()
            sys.stderr.flush()

    if config.tracer:
        sys.settrace(None)
        results = config.tracer.results()
        results.write_results(
            show_missing=True, summary=False, coverdir=config.coverdir().path
        )


if __name__ == "__main__":
    main(_captureSysStdout=True)
