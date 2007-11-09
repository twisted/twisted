# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.selectreactor} which do not
necessarily use the public interfaces exported by that reactor.
"""

from twisted.internet.abstract import FileDescriptor
from twisted.internet.selectreactor import SelectReactor

from twisted.trial.unittest import TestCase


class SelectReactorTests(TestCase):
    """
    Tests for L{SelectReactor}.
    """
    def setUp(self):
        """
        Create an instance of L{SelectReactor} to be used by tests.
        """
        self.reactor = SelectReactor()


    def test_preenDescriptorsDisconnectsSelectable(self):
        """
        L{SelectReactor._preenDescriptors} should find bad file-descriptors and
        disconnect the selectable associated with them.
        """
        lostConnection = []
        selectable = FileDescriptor(self.reactor)
        selectable.fileno = lambda: -1
        selectable.connectionLost = lostConnection.append
        self.reactor.addReader(selectable)
        self.reactor._preenDescriptors()
        self.assertEqual(len(lostConnection), 1)
        lostConnection[0].trap(ValueError)
