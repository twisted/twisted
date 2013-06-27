# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names.resolve}.
"""

from twisted.trial.unittest import TestCase
from twisted.names.error import DomainError
from twisted.names.resolve import ResolverChain



class ResolverChainTests(TestCase):
    """
    Tests for L{twisted.names.resolve.ResolverChain}
    """

    def test_emptyResolversList(self):
        """
        If L{ResolverChain} is instantiated with an empty C{resolvers}
        list, a L{ResolverChainConstructionError} is raised.
        """
        r = ResolverChain([])
        d = r.lookupAddress('www.example.com')
        f = self.failureResultOf(d)
        self.assertIs(f.trap(DomainError), DomainError)
