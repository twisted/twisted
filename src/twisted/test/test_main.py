# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test that twisted scripts can be invoked as modules.
"""

from __future__ import division, absolute_import

import sys

from twisted.application.twist._options import TwistOptions
from twisted.internet import defer, reactor
from twisted.python.compat import NativeStringIO as StringIO
from twisted.test.test_process import Accumulator
from twisted.trial.unittest import TestCase


class MainTests(TestCase):
    """Test that twisted scripts can be invoked as modules."""
    def test_twisted(self):
        """Invoking python -m twisted should execute twist."""
        cmd = sys.executable
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        reactor.spawnProcess(p, cmd, [cmd, '-m', 'twisted', '--help'], env=None)
        p.transport.closeStdin()

        def processEnded(ign):
            f = p.outF
            output = f.getvalue().replace(b'\r\n', b'\n')

            options = TwistOptions()
            message = '{}\n'.format(options).encode('utf-8')
            self.assertEqual(output, message)
        return d.addCallback(processEnded)

    def test_twisted_import(self):
        """Importing twisted.__main__ does not execute twist."""
        output = StringIO()
        monkey = self.patch(sys, 'stdout', output)

        import twisted.__main__
        self.assertTrue(twisted.__main__)  # Appease pyflakes

        monkey.restore()
        self.assertEqual(output.getvalue(), "")
