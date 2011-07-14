# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.default}.
"""

try:
    from select import poll
except ImportError:
    pollSkip = "select.poll() unavailable on this platform"
else:
    pollSkip = None

from twisted.trial.unittest import TestCase
from twisted.python.runtime import Platform
from twisted.internet.default import _getInstallFunction

linux = Platform('posix', 'linux2')
windows = Platform('nt', 'win32')
osx = Platform('posix', 'darwin')


class PollReactorTests(TestCase):
    """
    Tests for the cases of L{twisted.internet.default._getInstallFunction}
    in which it picks the poll(2)-based reactor.
    """
    skip = pollSkip

    def test_linux(self):
        """
        L{_getInstallFunction} chooses the poll reactor on Linux.
        """
        install = _getInstallFunction(linux)
        self.assertEqual(
            install.__module__, 'twisted.internet.pollreactor')



class SelectReactorTests(TestCase):
    """
    Tests for the cases of L{twisted.internet.default._getInstallFunction}
    in which it picks the select(2)-based reactor.
    """
    def test_osx(self):
        """
        L{_getInstallFunction} chooses the select reactor on OS X.
        """
        install = _getInstallFunction(osx)
        self.assertEqual(
            install.__module__, 'twisted.internet.selectreactor')


    def test_windows(self):
        """
        L{_getInstallFunction} chooses the select reactor on Windows.
        """
        install = _getInstallFunction(windows)
        self.assertEqual(
            install.__module__, 'twisted.internet.selectreactor')
