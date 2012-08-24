# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the parts of L{twisted.python.reflect} which have been ported to
Python 3.
"""

from __future__ import division, absolute_import

# Switch to SynchronousTestCase as part of #5885:
from unittest import TestCase

from twisted.python._reflectpy3 import accumulateMethods, prefixedMethods


class Base(object):
    """
    A no-op class which can be used to verify the behavior of method-discovering
    APIs.
    """
    def method(self):
        """
        A no-op method which can be discovered.
        """



class Sub(Base):
    """
    A subclass of a class with a method which can be discovered.
    """



class Separate(object):
    """
    A no-op class with methods with differing prefixes.
    """
    def good_method(self):
        """
        A no-op method which a matching prefix to be discovered.
        """


    def bad_method(self):
        """
        A no-op method with a mismatched prefix to not be discovered.
        """



class AccumulateMethodsTests(TestCase):
    """
    Tests for L{accumulateMethods} which finds methods on a class hierarchy and
    adds them to a dictionary.
    """
    def test_ownClass(self):
        """
        If x is and instance of Base} and Base defines a method named method,
        L{accumulateMethods} adds an item to the given dictionary with
        C{"method"} as the key and a bound method object for Base.method value.
        """
        x = Base()
        output = {}
        accumulateMethods(x, output)
        self.assertEqual({"method": x.method}, output)


    def test_baseClass(self):
        """
        If x is an instance of Sub and Sub is a subclass of Base and Base
        defines a method named method, L{accumulateMethods} adds an item to the
        given dictionary with C{"method"} as the key and a bound method object
        for Base.method as the value.
        """
        x = Sub()
        output = {}
        accumulateMethods(x, output)
        self.assertEqual({"method": x.method}, output)


    def test_prefix(self):
        """
        If a prefix is given, L{accumulateMethods} limits its results to methods
        beginning with that prefix.  Keys in the resulting dictionary also have
        the prefix removed from them.
        """
        x = Separate()
        output = {}
        accumulateMethods(x, output, 'good_')
        self.assertEqual({'method': x.good_method}, output)



class PrefixedMethodsTests(TestCase):
    """
    Tests for L{prefixedMethods} which finds methods on a class hierarchy and
    adds them to a dictionary.
    """
    def test_onlyObject(self):
        """
        L{prefixedMethods} returns a list of the methods discovered on an
        object.
        """
        x = Base()
        output = prefixedMethods(x)
        self.assertEqual([x.method], output)


    def test_prefix(self):
        """
        If a prefix is given, L{prefixedMethods} returns only methods named with
        that prefix.
        """
        x = Separate()
        output = prefixedMethods(x, 'good_')
        self.assertEqual([x.good_method], output)
