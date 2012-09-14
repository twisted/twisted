# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.main}.
"""

from __future__ import division, absolute_import

from twisted.trial import unittest
import twisted.internet
from twisted.internet.error import ReactorAlreadyInstalledError
from twisted.internet.main import installReactor
from twisted.test.test_twisted import SetAsideModule

class NoReactor(SetAsideModule):
    """
    Context manager that uninstalls the reactor, if any.
    """

    def __init__(self):
        SetAsideModule.__init__(self, "twisted.internet.reactor")


    def __enter__(self):
        SetAsideModule.__enter__(self)
        if "twisted.internet.reactor" in self.modules:
            del twisted.internet.reactor


    def __exit__(self, excType, excValue, traceback):
        SetAsideModule.__exit__(self, excType, excValue, traceback)
        # Clean up 'reactor' attribute that may have been set on
        # twisted.internet:
        reactor = self.modules.get("twisted.internet.reactor", None)
        if reactor is not None:
            twisted.internet.reactor = reactor
        else:
            try:
                del twisted.internet.reactor
            except AttributeError:
                pass



class InstallReactorTests(unittest.SynchronousTestCase):
    """
    Tests for L{installReactor}.
    """

    def test_installReactor(self):
        """
        L{installReactor} installs a new reactor if none is present.
        """
        with NoReactor():
            newReactor = object()
            installReactor(newReactor)
            from twisted.internet import reactor
            self.assertIdentical(newReactor, reactor)


    def test_alreadyInstalled(self):
        """
        If a reactor is already installed, L{installReactor} raises
        L{ReactorAlreadyInstalledError}.
        """
        with NoReactor():
            installReactor(object())
            self.assertRaises(ReactorAlreadyInstalledError, installReactor,
                              object())


    def test_errorIsAnAssertionError(self):
        """
        For backwards compatibility, L{ReactorAlreadyInstalledError} is an
        L{AssertionError}.
        """
        self.assertTrue(issubclass(ReactorAlreadyInstalledError,
                        AssertionError))
