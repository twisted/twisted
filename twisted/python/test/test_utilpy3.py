# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the subset of L{twisted.python.util} which has been ported to Python 3.
"""

from __future__ import division, absolute_import

import sys, errno, warnings

from twisted.trial.unittest import SynchronousTestCase as TestCase

from twisted.python import _utilpy3 as util


class Record(util.FancyEqMixin):
    """
    Trivial user of L{FancyEqMixin} used by tests.
    """
    compareAttributes = ('a', 'b')

    def __init__(self, a, b):
        self.a = a
        self.b = b



class DifferentRecord(util.FancyEqMixin):
    """
    Trivial user of L{FancyEqMixin} which is not related to L{Record}.
    """
    compareAttributes = ('a', 'b')

    def __init__(self, a, b):
        self.a = a
        self.b = b



class DerivedRecord(Record):
    """
    A class with an inheritance relationship to L{Record}.
    """



class EqualToEverything(object):
    """
    A class the instances of which consider themselves equal to everything.
    """
    def __eq__(self, other):
        return True


    def __ne__(self, other):
        return False



class EqualToNothing(object):
    """
    A class the instances of which consider themselves equal to nothing.
    """
    def __eq__(self, other):
        return False


    def __ne__(self, other):
        return True



class EqualityTests(TestCase):
    """
    Tests for L{FancyEqMixin}.
    """
    def test_identity(self):
        """
        Instances of a class which mixes in L{FancyEqMixin} but which
        defines no comparison attributes compare by identity.
        """
        class Empty(util.FancyEqMixin):
            pass

        self.assertFalse(Empty() == Empty())
        self.assertTrue(Empty() != Empty())
        empty = Empty()
        self.assertTrue(empty == empty)
        self.assertFalse(empty != empty)


    def test_equality(self):
        """
        Instances of a class which mixes in L{FancyEqMixin} should compare
        equal if all of their attributes compare equal.  They should not
        compare equal if any of their attributes do not compare equal.
        """
        self.assertTrue(Record(1, 2) == Record(1, 2))
        self.assertFalse(Record(1, 2) == Record(1, 3))
        self.assertFalse(Record(1, 2) == Record(2, 2))
        self.assertFalse(Record(1, 2) == Record(3, 4))


    def test_unequality(self):
        """
        Unequality between instances of a particular L{record} should be
        defined as the negation of equality.
        """
        self.assertFalse(Record(1, 2) != Record(1, 2))
        self.assertTrue(Record(1, 2) != Record(1, 3))
        self.assertTrue(Record(1, 2) != Record(2, 2))
        self.assertTrue(Record(1, 2) != Record(3, 4))


    def test_differentClassesEquality(self):
        """
        Instances of different classes which mix in L{FancyEqMixin} should not
        compare equal.
        """
        self.assertFalse(Record(1, 2) == DifferentRecord(1, 2))


    def test_differentClassesInequality(self):
        """
        Instances of different classes which mix in L{FancyEqMixin} should
        compare unequal.
        """
        self.assertTrue(Record(1, 2) != DifferentRecord(1, 2))


    def test_inheritedClassesEquality(self):
        """
        An instance of a class which derives from a class which mixes in
        L{FancyEqMixin} should compare equal to an instance of the base class
        if and only if all of their attributes compare equal.
        """
        self.assertTrue(Record(1, 2) == DerivedRecord(1, 2))
        self.assertFalse(Record(1, 2) == DerivedRecord(1, 3))
        self.assertFalse(Record(1, 2) == DerivedRecord(2, 2))
        self.assertFalse(Record(1, 2) == DerivedRecord(3, 4))


    def test_inheritedClassesInequality(self):
        """
        An instance of a class which derives from a class which mixes in
        L{FancyEqMixin} should compare unequal to an instance of the base
        class if any of their attributes compare unequal.
        """
        self.assertFalse(Record(1, 2) != DerivedRecord(1, 2))
        self.assertTrue(Record(1, 2) != DerivedRecord(1, 3))
        self.assertTrue(Record(1, 2) != DerivedRecord(2, 2))
        self.assertTrue(Record(1, 2) != DerivedRecord(3, 4))


    def test_rightHandArgumentImplementsEquality(self):
        """
        The right-hand argument to the equality operator is given a chance
        to determine the result of the operation if it is of a type
        unrelated to the L{FancyEqMixin}-based instance on the left-hand
        side.
        """
        self.assertTrue(Record(1, 2) == EqualToEverything())
        self.assertFalse(Record(1, 2) == EqualToNothing())


    def test_rightHandArgumentImplementsUnequality(self):
        """
        The right-hand argument to the non-equality operator is given a
        chance to determine the result of the operation if it is of a type
        unrelated to the L{FancyEqMixin}-based instance on the left-hand
        side.
        """
        self.assertFalse(Record(1, 2) != EqualToEverything())
        self.assertTrue(Record(1, 2) != EqualToNothing())



class UnsignedIDTests(TestCase):
    """
    Tests for L{util.unsignedID} and L{util.setIDFunction}.
    """

    def setUp(self):
        """
        Save the value of L{util._idFunction} and arrange for it to be restored
        after the test runs.
        """
        self.addCleanup(setattr, util, '_idFunction', util._idFunction)


    def test_setIDFunction(self):
        """
        L{util.setIDFunction} returns the last value passed to it.
        """
        value = object()
        previous = util.setIDFunction(value)
        result = util.setIDFunction(previous)
        self.assertIdentical(value, result)


    def test_unsignedID(self):
        """
        L{util.unsignedID} uses the function passed to L{util.setIDFunction} to
        determine the unique integer id of an object and then adjusts it to be
        positive if necessary.
        """
        foo = object()
        bar = object()

        # A fake object identity mapping
        objects = {foo: 17, bar: -73}
        def fakeId(obj):
            return objects[obj]

        util.setIDFunction(fakeId)

        self.assertEqual(util.unsignedID(foo), 17)
        self.assertEqual(util.unsignedID(bar), (sys.maxsize + 1) * 2 - 73)


    def test_defaultIDFunction(self):
        """
        L{util.unsignedID} uses the built in L{id} by default.
        """
        obj = object()
        idValue = id(obj)
        if idValue < 0:
            idValue += (sys.maxsize + 1) * 2

        self.assertEqual(util.unsignedID(obj), idValue)



class UntilConcludesTests(TestCase):
    """
    Tests for L{untilConcludes}, an C{EINTR} helper.
    """
    def test_uninterruptably(self):
        """
        L{untilConcludes} calls the function passed to it until the function
        does not raise either L{OSError} or L{IOError} with C{errno} of
        C{EINTR}.  It otherwise completes with the same result as the function
        passed to it.
        """
        def f(a, b):
            self.calls += 1
            exc = self.exceptions.pop()
            if exc is not None:
                raise exc(errno.EINTR, "Interrupted system call!")
            return a + b

        self.exceptions = [None]
        self.calls = 0
        self.assertEqual(util.untilConcludes(f, 1, 2), 3)
        self.assertEqual(self.calls, 1)

        self.exceptions = [None, OSError, IOError]
        self.calls = 0
        self.assertEqual(util.untilConcludes(f, 2, 3), 5)
        self.assertEqual(self.calls, 3)



class SuppressedWarningsTests(TestCase):
    """
    Tests for L{util.runWithWarningsSuppressed}.
    """
    runWithWarningsSuppressed = staticmethod(util.runWithWarningsSuppressed)

    def test_runWithWarningsSuppressedFiltered(self):
        """
        Warnings from the function called by C{runWithWarningsSuppressed} are
        suppressed if they match the passed in filter.
        """
        filters = [(("ignore", ".*foo.*"), {}),
                   (("ignore", ".*bar.*"), {})]
        self.runWithWarningsSuppressed(filters, warnings.warn, "ignore foo")
        self.runWithWarningsSuppressed(filters, warnings.warn, "ignore bar")
        self.assertEqual([], self.flushWarnings())


    def test_runWithWarningsSuppressedUnfiltered(self):
        """
        Warnings from the function called by C{runWithWarningsSuppressed} are
        not suppressed if they do not match the passed in filter.
        """
        filters = [(("ignore", ".*foo.*"), {}),
                   (("ignore", ".*bar.*"), {})]
        self.runWithWarningsSuppressed(filters, warnings.warn, "don't ignore")
        self.assertEqual(
            ["don't ignore"], [w['message'] for w in self.flushWarnings()])


    def test_passThrough(self):
        """
        C{runWithWarningsSuppressed} returns the result of the function it
        called.
        """
        self.assertEqual(self.runWithWarningsSuppressed([], lambda: 4), 4)


    def test_noSideEffects(self):
        """
        Once C{runWithWarningsSuppressed} has returned, it no longer
        suppresses warnings.
        """
        filters = [(("ignore", ".*foo.*"), {}),
                   (("ignore", ".*bar.*"), {})]
        self.runWithWarningsSuppressed(filters, lambda: None)
        warnings.warn("ignore foo")
        self.assertEqual(
            ["ignore foo"], [w['message'] for w in self.flushWarnings()])



class FancyStrMixinTests(TestCase):
    """
    Tests for L{util.FancyStrMixin}.
    """

    def test_sequenceOfStrings(self):
        """
        If C{showAttributes} is set to a sequence of strings, C{__str__}
        renders using those by looking them up as attributes on the object.
        """
        class Foo(util.FancyStrMixin):
            showAttributes = ("first", "second")
            first = 1
            second = "hello"
        self.assertEqual(str(Foo()), "<Foo first=1 second='hello'>")


    def test_formatter(self):
        """
        If C{showAttributes} has an item that is a 2-tuple, C{__str__} renders
        the first item in the tuple as a key and the result of calling the
        second item with the value of the attribute named by the first item as
        the value.
        """
        class Foo(util.FancyStrMixin):
            showAttributes = (
                "first",
                ("second", lambda value: repr(value[::-1])))
            first = "hello"
            second = "world"
        self.assertEqual("<Foo first='hello' second='dlrow'>", str(Foo()))


    def test_override(self):
        """
        If C{showAttributes} has an item that is a 3-tuple, C{__str__} renders
        the second item in the tuple as a key, and the contents of the
        attribute named in the first item are rendered as the value. The value
        is formatted using the third item in the tuple.
        """
        class Foo(util.FancyStrMixin):
            showAttributes = ("first", ("second", "2nd", "%.1f"))
            first = 1
            second = 2.111
        self.assertEqual(str(Foo()), "<Foo first=1 2nd=2.1>")


    def test_fancybasename(self):
        """
        If C{fancybasename} is present, C{__str__} uses it instead of the class name.
        """
        class Foo(util.FancyStrMixin):
            fancybasename = "Bar"
        self.assertEqual(str(Foo()), "<Bar>")


    def test_repr(self):
        """
        C{__repr__} outputs the same content as C{__str__}.
        """
        class Foo(util.FancyStrMixin):
            showAttributes = ("first", "second")
            first = 1
            second = "hello"
        obj = Foo()
        self.assertEqual(str(obj), repr(obj))



class NameToLabelTests(TestCase):
    """
    Tests for L{nameToLabel}.
    """

    def test_nameToLabel(self):
        """
        Test the various kinds of inputs L{nameToLabel} supports.
        """
        nameData = [
            ('f', 'F'),
            ('fo', 'Fo'),
            ('foo', 'Foo'),
            ('fooBar', 'Foo Bar'),
            ('fooBarBaz', 'Foo Bar Baz'),
            ]
        for inp, out in nameData:
            got = util.nameToLabel(inp)
            self.assertEqual(
                got, out,
                "nameToLabel(%r) == %r != %r" % (inp, got, out))



class InsensitiveDictTest(TestCase):
    """
    Tests for L{util.InsensitiveDict}.
    """

    def test_preserve(self):
        """
        L{util.InsensitiveDict} preserves the case of keys if constructed with
        C{preserve=True}.
        """
        dct = util.InsensitiveDict({'Foo':'bar', 1:2, 'fnz':{1:2}}, preserve=1)
        self.assertEqual(dct['fnz'], {1:2})
        self.assertEqual(dct['foo'], 'bar')
        self.assertEqual(dct.copy(), dct)
        self.assertEqual(dct['foo'], dct.get('Foo'))
        self.assertIn(1, dct)
        self.assertIn('foo', dct)
        # Make eval() work, urrrrgh:
        InsensitiveDict = util.InsensitiveDict
        self.assertEqual(eval(repr(dct)), dct)
        keys=['Foo', 'fnz', 1]
        for x in keys:
            self.assertIn(x, dct.keys())
            self.assertIn((x, dct[x]), dct.items())
        self.assertEqual(len(keys), len(dct))
        del dct[1]
        del dct['foo']
        self.assertEqual(dct.keys(), ['fnz'])


    def test_noPreserve(self):
        """
        L{util.InsensitiveDict} does not preserves the case of keys if
        constructed with C{preserve=False}.
        """
        dct = util.InsensitiveDict({'Foo':'bar', 1:2, 'fnz':{1:2}}, preserve=0)
        keys=['foo', 'fnz', 1]
        for x in keys:
            self.assertIn(x, dct.keys())
            self.assertIn((x, dct[x]), dct.items())
        self.assertEqual(len(keys), len(dct))
        del dct[1]
        del dct['foo']
        self.assertEqual(dct.keys(), ['fnz'])


    def test_unicode(self):
        """
        Unicode keys are case insensitive.
        """
        d = util.InsensitiveDict(preserve=False)
        d[u"Foo"] = 1
        self.assertEqual(d[u"FOO"], 1)
        self.assertEqual(d.keys(), [u"foo"])


    def test_bytes(self):
        """
        Bytes keys are case insensitive.
        """
        d = util.InsensitiveDict(preserve=False)
        d[b"Foo"] = 1
        self.assertEqual(d[b"FOO"], 1)
        self.assertEqual(d.keys(), [b"foo"])
