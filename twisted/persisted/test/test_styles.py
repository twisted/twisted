# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.persisted.styles}.
"""

import pickle

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



def sampleFunction():
    """
    A sample function for pickling.
    """



lambdaExample = lambda x: x



class UnpickleMethodTests(unittest.TestCase):
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


    def test_primeDirective(self):
        """
        We do not contaminate normal function pickling with concerns from
        Twisted.
        """
        def expected(n):
            return "\n".join([
                    "c" + __name__,
                    sampleFunction.__name__, "p" + n, "."
                ]).encode("ascii")
        self.assertEqual(pickle.dumps(sampleFunction, protocol=0),
                         expected("0"))
        try:
            import cPickle
        except:
            pass
        else:
            self.assertEqual(
                cPickle.dumps(sampleFunction, protocol=0),
                expected("1")
            )


    def test_lambdaRaisesPicklingError(self):
        """
        Pickling a C{lambda} function ought to raise a L{pickle.PicklingError}.
        """
        self.assertRaises(pickle.PicklingError, pickle.dumps, lambdaExample)
        try:
            import cPickle
        except:
            pass
        else:
            self.assertRaises(cPickle.PicklingError, cPickle.dumps,
                              lambdaExample)
