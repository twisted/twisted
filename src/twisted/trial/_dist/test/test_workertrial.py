# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.trial._dist.workertrial}.
"""

import errno
import sys
import os

from io import BytesIO

from twisted.protocols.amp import AMP
from twisted.test.proto_helpers import StringTransport
from twisted.trial.unittest import TestCase
from twisted.trial._dist.workertrial import (
    WorkerLogObserver,
    main,
    _setupPath,
    WorkerStdout,
)
from twisted.trial._dist import (
    workertrial,
    _WORKER_AMP_STDIN,
    _WORKER_AMP_STDOUT,
    workercommands,
    managercommands,
)


class FakeAMP(AMP):
    """
    A fake amp protocol.
    """


class AMPSpyClient:
    """
    Test helper to records the AMP remote calls.
    """

    def __init__(self, calls: list):
        self._calls = calls

    def callRemote(self, method, **kwargs):
        self._calls.append((method, kwargs))


class WorkerLogObserverTests(TestCase):
    """
    Tests for L{WorkerLogObserver}.
    """

    def test_emit(self):
        """
        L{WorkerLogObserver} forwards data to L{managercommands.TestWrite}.
        """
        calls = []
        observer = WorkerLogObserver(AMPSpyClient(calls))
        observer.emit({"message": ["Some log"]})
        self.assertEqual(calls, [(managercommands.TestWrite, {"out": "Some log"})])


class WorkerStdoutTests(TestCase):
    """
    Tests for L{WorkerStdout}.
    """

    def test_write(self):
        """
        L{WorkerStdout} forwards data to L{managercommands.TestWrite} without
        any extra processing.
        """
        calls = []
        stdout = WorkerStdout(AMPSpyClient(calls))

        stdout.write("Her comes the \N{sun}!")

        self.assertEqual(
            calls, [(managercommands.TestWrite, {"out": "Her comes the \N{sun}!"})]
        )

    def test_write_bytes(self):
        """
        Raises TypeError when a non string value is written.
        """
        calls = []
        stdout = WorkerStdout(AMPSpyClient(calls))

        error = self.assertRaises(TypeError, stdout.write, b"\xe2\x99")

        self.assertEqual("string argument expected, got <class 'type'>", error.args[0])

    def test_integration(self):
        """
        This test is here to trigger a write to sys.stdout for which
        when running in distributed trial workers the value is forwarded to
        the centralized log.

        It's kind of a manual test, as there is no automatic assertion.
        When call as
        C{trial -j1 twisted.trial._dist.test.test_workertrial.WorkerStdoutTests.test_integration}

        You should see the message via C{cat _trial_temp/0/test.log}
        """
        sys.stdout.write("Hello from \N{sun}y worker!")
        sys.stdout.flush()


class MainTests(TestCase):
    """
    Tests for L{main}.
    """

    def setUp(self):
        self.readStream = BytesIO()
        self.writeStream = BytesIO()
        self.patch(
            workertrial, "startLoggingWithObserver", self.startLoggingWithObserver
        )
        self.addCleanup(setattr, sys, "argv", sys.argv)
        sys.argv = ["trial"]

    def fdopen(self, fd, mode=None):
        """
        Fake C{os.fdopen} implementation which returns C{self.readStream} for
        the stdin fd and C{self.writeStream} for the stdout fd.
        """
        if fd == _WORKER_AMP_STDIN:
            self.assertIdentical("rb", mode)
            return self.readStream
        elif fd == _WORKER_AMP_STDOUT:
            self.assertEqual("wb", mode)
            return self.writeStream
        else:
            raise AssertionError(f"Unexpected fd {fd!r}")

    def startLoggingWithObserver(self, emit, setStdout):
        """
        Override C{startLoggingWithObserver} for not starting logging.
        """
        self.assertFalse(setStdout)

    def test_empty(self):
        """
        If no data is ever written, L{main} exits without writing data out.
        """
        main(self.fdopen)
        self.assertEqual(b"", self.writeStream.getvalue())

    def test_forwardCommand(self):
        """
        L{main} forwards data from its input stream to a L{WorkerProtocol}
        instance which writes data to the output stream.
        """
        client = FakeAMP()
        clientTransport = StringTransport()
        client.makeConnection(clientTransport)
        client.callRemote(workercommands.Run, testCase="doesntexist")
        self.readStream = clientTransport.io
        self.readStream.seek(0, 0)
        main(self.fdopen)
        self.assertIn(b"No module named 'doesntexist'", self.writeStream.getvalue())

    def test_readInterrupted(self):
        """
        If reading the input stream fails with a C{IOError} with errno
        C{EINTR}, L{main} ignores it and continues reading.
        """
        excInfos = []

        class FakeStream:
            count = 0

            def read(oself, size):
                oself.count += 1
                if oself.count == 1:
                    raise OSError(errno.EINTR)
                else:
                    excInfos.append(sys.exc_info())
                return b""

        self.readStream = FakeStream()
        main(self.fdopen)
        self.assertEqual(b"", self.writeStream.getvalue())
        self.assertEqual([(None, None, None)], excInfos)

    def test_otherReadError(self):
        """
        L{main} only ignores C{IOError} with C{EINTR} errno: otherwise, the
        error pops out.
        """

        class FakeStream:
            count = 0

            def read(oself, size):
                oself.count += 1
                if oself.count == 1:
                    raise OSError("Something else")
                return ""

        self.readStream = FakeStream()
        self.assertRaises(IOError, main, self.fdopen)

    def test_sysStdoutRedirection(self):
        """
        It will forward the text written to C{sys.stdout} inside the
        distributed trial sub-process via the AMP C{TestWrite} command.
        """
        # The patch is used so that at the end of the test we will have
        # the default C{sys.stdout} restored.
        # It also checks that C{sys.stdout} is not used inside main before
        # the C{sys.stdout} forwarding to remote AMP is setup.
        self.patch(sys, "stdout", None)

        main(_fdopen=self.fdopen, _captureSysStdout=True)

        # We keep a local reference to help with stepping into the debugger
        # here and the debugger would replace sys.stdout.
        stdout = sys.stdout
        self.assertIsInstance(stdout, WorkerStdout)

        # Will send the string value vai AMP.
        stdout.write("hello")
        self.assertEqual(
            b"\x00\x04_ask\x00\x011\x00\x08_command\x00\tTestWrite\x00\x03out\x00\x05hello\x00\x00",
            self.writeStream.getvalue(),
        )


class SetupPathTests(TestCase):
    """
    Tests for L{_setupPath} C{sys.path} manipulation.
    """

    def setUp(self):
        self.addCleanup(setattr, sys, "path", sys.path[:])

    def test_overridePath(self):
        """
        L{_setupPath} overrides C{sys.path} if B{TRIAL_PYTHONPATH} is specified
        in the environment.
        """
        environ = {"TRIAL_PYTHONPATH": os.pathsep.join(["foo", "bar"])}
        _setupPath(environ)
        self.assertEqual(["foo", "bar"], sys.path)

    def test_noVariable(self):
        """
        L{_setupPath} doesn't change C{sys.path} if B{TRIAL_PYTHONPATH} is not
        present in the environment.
        """
        originalPath = sys.path[:]
        _setupPath({})
        self.assertEqual(originalPath, sys.path)
