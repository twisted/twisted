# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for various parts of L{twisted.web}.
"""

from twisted.internet import defer
from twisted.trial import unittest

from twisted.web import client

class DummyEndPoint(object):

    def __init__(self, someString):
        self.someString = someString

    def __repr__(self):
        return 'DummyEndPoint({})'.format(self.someString)

    def connect(self, factory):
        return defer.succeed(dict(factory=factory))

class HTTPConnectionPool(unittest.TestCase):
    """
    Unit tests for L{client._HTTP11ClientFactory}.
    """

    def test_repr(self):
        pool = client.HTTPConnectionPool(reactor=None)
        ep = DummyEndPoint("this_is_probably_unique")
        d = pool.getConnection('someplace', ep)
        l = []
        d.addCallback(l.append)
        result, = l
        representation = repr(result)
        self.assertIn("this_is_probably_unique", representation)
