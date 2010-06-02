# Copyright (c) 2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Whitebox tests for the Gtk2-based reactor.
"""

from os import listdir

from twisted.trial.unittest import TestCase
try:
    from twisted.internet.gtk2reactor import Gtk2Reactor
except ImportError, e:
    skip = "gtk2reactor unavailable (%r)" % (e,)


def enumerateFileDescriptors():
    return map(int, listdir('/proc/self/fd'))




class Gtk2ReactorTests(TestCase):
    """
    Tests for L{Gtk2Reactor}.
    """
    def test_fileDescriptorsCleanedUp(self):
        """
        Any file descriptors created by running L{Gtk2Reactor} are destroyed by
        the time C{reactor.run()} returns.
        """
        before = enumerateFileDescriptors()
        reactor = Gtk2Reactor(useGtk=False)
        reactor.callWhenRunning(reactor.stop)
        reactor.run()
        import gc; gc.collect()
        after = enumerateFileDescriptors()
        self.assertEquals(before, after)
