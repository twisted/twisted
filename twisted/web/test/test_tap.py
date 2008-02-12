# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.tap}.
"""

from twisted.trial.unittest import TestCase

from twisted.web.server import Site
from twisted.web.static import Data
from twisted.web.distrib import ResourcePublisher
from twisted.web.tap import makePersonalServerFactory

from twisted.spread.pb import PBServerFactory


class ServiceTests(TestCase):
    """
    Tests for the service creation APIs in L{twisted.web.tap}.
    """
    def test_makePersonalServerFactory(self):
        """
        L{makePersonalServerFactory} returns a PB server factory which has
        as its root object a L{ResourcePublisher}.
        """
        # The fact that this pile of objects can actually be used somehow is
        # verified by twisted.web.test.test_distrib.
        site = Site(Data("foo bar", "text/plain"))
        serverFactory = makePersonalServerFactory(site)
        self.assertIsInstance(serverFactory, PBServerFactory)
        self.assertIsInstance(serverFactory.root, ResourcePublisher)
        self.assertIdentical(serverFactory.root.site, site)
