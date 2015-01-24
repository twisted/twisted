# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.persisted.styles}.
"""

from twisted.trial import unittest
from twisted.persisted.styles import unpickleMethod


class Foo:
    """
    Helper class.
    """
    def method(self):
        """
        Helper method.
        """



class Bar:
    """
    Helper class.
    """



class UnpickleMethodTestCase(unittest.TestCase):
    """
    Tests for the unpickleMethod function.
    """

    def test_instanceBuildingNamePresent(self):
        """
        L{unpickleMethod} returns an instance method bound to the
        instance passed to it.
        """
        foo = Foo()
        m = unpickleMethod('method', foo, Foo)
        self.assertEqual(m, foo.method)
        self.assertNotIdentical(m, foo.method)


    def test_instanceBuildingNameNotPresent(self):
        """
        If the named method is not present in the class,
        L{unpickleMethod} finds a method on the class of the instance
        and returns a bound method from there.
        """
        foo = Foo()
        m = unpickleMethod('method', foo, Bar)
        self.assertEqual(m, foo.method)
        self.assertNotIdentical(m, foo.method)
