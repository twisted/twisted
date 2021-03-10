# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test that twisted scripts can be invoked as modules.
"""


import sys
from io import StringIO

from twisted.application.twist._options import TwistOptions
from twisted.scripts import trial
from twisted.internet import defer, reactor
from twisted.test.test_process import Accumulator
from twisted.trial.unittest import TestCase


class MainTests(TestCase):
    """Test that twisted scripts can be invoked as modules."""

    # Force the full diff to make debugging easier on failures.
    maxDiff = None

    def test_twisted(self):
        """Invoking python -m twisted should execute twist."""
        cmd = sys.executable
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        # Enforce 80 columns as otherwise the test are failing when executed in debug mode.
        reactor.spawnProcess(
            p, cmd, [cmd, "-m", "twisted", "--help"], env={"COLUMNS": "80"}
        )
        p.transport.closeStdin()

        # Fix up our sys args to match the command we issued
        from twisted import __main__

        self.patch(sys, "argv", [__main__.__file__, "--help"])

        def processEnded(ign):
            f = p.outF
            output = f.getvalue()

            options = TwistOptions()
            message = f"{options}\n".encode("utf-8")
            self.assertEqual(output.splitlines(), message.splitlines())

        return d.addCallback(processEnded)

    def test_trial(self):
        """Invoking python -m twisted.trial should execute trial."""
        cmd = sys.executable
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        # Enforce 80 columns as otherwise the test are failing when executed in debug mode.
        reactor.spawnProcess(
            p, cmd, [cmd, "-m", "twisted.trial", "--help"], env={"COLUMNS": "80"}
        )
        p.transport.closeStdin()

        # Fix up our sys args to match the command we issued
        from twisted.trial import __main__

        self.patch(sys, "argv", [__main__.__file__, "--help"])

        def processEnded(ign):
            f = p.outF
            output = f.getvalue()

            options = trial.Options()
            message = f"{options}\n".encode("utf-8")
            self.assertEqual(output.splitlines(), message.splitlines())

        return d.addCallback(processEnded)

    def test_twisted_import(self):
        """Importing twisted.__main__ does not execute twist."""
        output = StringIO()
        monkey = self.patch(sys, "stdout", output)

        import twisted.__main__

        self.assertTrue(twisted.__main__)  # Appease pyflakes

        monkey.restore()
        self.assertEqual(output.getvalue(), "")
