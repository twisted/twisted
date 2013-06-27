# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names.resolve}.
"""

from twisted.trial.unittest import TestCase
from twisted.names.resolve import ResolverChain, ResolverChainConstructionError



class ResolverChainTests(TestCase):
    """
    Tests for L{twisted.names.resolve.ResolverChain}
    """

    def test_emptyResolversList(self):
        """
        If L{ResolverChain} is instantiated with an empty C{resolvers}
        list, a L{ResolverChainConstructionError} is raised.
        """
        self.assertRaises(
            ResolverChainConstructionError, ResolverChain, resolvers=[])
