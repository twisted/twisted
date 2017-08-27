# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for various parts of L{twisted.web}.
"""

from twisted.trial import unittest

from twisted.web import client

class HTTP11FactoryTest(unittest.TestCase):
    """
    Unit tests for L{client._HTTP11ClientFactory}.
    """

    def test_repr(self):
        def a_special_name():
            pass
        factory = client._HTTP11ClientFactory(a_special_name, 'this_is_kinda_unique')
        result = repr(factory)
        self.assertIn('a_special_name', result)
        self.assertIn('this_is_kinda_unique', result)
