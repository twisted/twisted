# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.default}.
"""

import select
from twisted.trial.unittest import TestCase
from twisted.python.runtime import Platform
from twisted.internet.default import _getInstallFunction

unix = Platform('posix', 'other')
linux = Platform('posix', 'linux2')
windows = Platform('nt', 'win32')
osx = Platform('posix', 'darwin')


class PollReactorTests(TestCase):
    """
    Tests for the cases of L{twisted.internet.default._getInstallFunction}
    in which it picks the poll(2) or epoll(7)-based reactors.
    """

    def assertIsPoll(self, install):
        """
        Assert the given function will install the poll() reactor, or select()
        if poll() is unavailable.
        """
        if hasattr(select, "poll"):
            self.assertEqual(
                install.__module__, 'twisted.internet.pollreactor')
        else:
            self.assertEqual(
                install.__module__, 'twisted.internet.selectreactor')


    def test_unix(self):
        """
        L{_getInstallFunction} chooses the poll reactor on arbitrary Unix
        platforms, falling back to select(2) if it is unavailable.
        """
        install = _getInstallFunction(unix)
        self.assertIsPoll(install)


    def test_linux(self):
        """
        L{_getInstallFunction} chooses the epoll reactor on Linux, or poll if
        epoll is unavailable.
        """
        install = _getInstallFunction(linux)
        try:
            from twisted.internet import epollreactor
        except ImportError:
            self.assertIsPoll(install)
        else:
            self.assertEqual(
                install.__module__, 'twisted.internet.epollreactor')



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
