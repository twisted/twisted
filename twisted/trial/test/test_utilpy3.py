# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""
Tests for the parts of L{twisted.trial.util} which have been ported to Python 3.
"""

from __future__ import division, absolute_import

from unittest import TestCase

from twisted.python.failure import Failure
from twisted.trial._utilpy3 import excInfoOrFailureToExcInfo, acquireAttribute


class ExcInfoTests(TestCase):
    """
    Tests for L{excInfoOrFailureToExcInfo}.
    """
    def test_excInfo(self):
        """
        L{excInfoOrFailureToExcInfo} returns exactly what it is passed, if it is
        passed a tuple like the one returned by L{sys.exc_info}.
        """
        info = (ValueError, ValueError("foo"), None)
        self.assertTrue(info is excInfoOrFailureToExcInfo(info))


    def test_failure(self):
        """
        When called with a L{Failure} instance, L{excInfoOrFailureToExcInfo}
        returns a tuple like the one returned by L{sys.exc_info}, with the
        elements taken from the type, value, and traceback of the failure.
        """
        try:
            1 / 0
        except:
            f = Failure()
        self.assertEqual((f.type, f.value, f.tb), excInfoOrFailureToExcInfo(f))



class AcquireAttributeTests(TestCase):
    """
    Tests for L{acquireAttribute}.
    """
    def test_foundOnEarlierObject(self):
        """
        The value returned by L{acquireAttribute} is the value of the requested
        attribute on the first object in the list passed in which has that
        attribute.
        """
        self.value = value = object()
        self.assertTrue(value is acquireAttribute([self, object()], "value"))


    def test_foundOnLaterObject(self):
        """
        The same as L{test_foundOnEarlierObject}, but for the case where the 2nd
        element in the object list has the attribute and the first does not.
        """
        self.value = value = object()
        self.assertTrue(value is acquireAttribute([object(), self], "value"))


    def test_notFoundException(self):
        """
        If none of the objects passed in the list to L{acquireAttribute} have
        the requested attribute, L{AttributeError} is raised.
        """
        self.assertRaises(AttributeError, acquireAttribute, [object()], "foo")


    def test_notFoundDefault(self):
        """
        If none of the objects passed in the list to L{acquireAttribute} have
        the requested attribute and a default value is given, the default value
        is returned.
        """
        default = object()
        self.assertTrue(default is acquireAttribute([object()], "foo", default))
