# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.test.iosim}.
"""

from twisted.test.iosim import FakeTransport
from twisted.trial.unittest import TestCase

class FakeTransportTests(TestCase):
    """
    Tests for L{FakeTransport}
    """

    def test_connectionSerial(self):
        """
        Each L{FakeTransport} receives a serial number that uniquely identifies
        it.
        """
        a = FakeTransport(object(), True)
        b = FakeTransport(object(), False)
        self.assertIsInstance(a.serial, int)
        self.assertIsInstance(b.serial, int)
        self.assertNotEqual(a.serial, b.serial)
