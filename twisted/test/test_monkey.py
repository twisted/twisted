# Copyright (c) 2007-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.monkey}.
"""

from twisted.trial import unittest

from twisted.python.monkey import MonkeyPatcher



class TestObj:
    def __init__(self):
        self.foo = 'foo value'
        self.bar = 'bar value'
        self.baz = 'baz value'



class MonkeyPatcherTest(unittest.TestCase):
    """
    Tests for L{MonkeyPatcher} monkey-patching class.
    """

    def setUp(self):
        self.testObject = TestObj()
        self.originalObject = TestObj()
        self.monkeyPatcher = MonkeyPatcher()


    def test_empty(self):
        """
        A monkey patcher without patches shouldn't change a thing.
        """
        self.monkeyPatcher.patch()

        # We can't assert that all state is unchanged, but at least we can
        # check our test object.
        self.assertEquals(self.originalObject.foo, self.testObject.foo)
        self.assertEquals(self.originalObject.bar, self.testObject.bar)
        self.assertEquals(self.originalObject.baz, self.testObject.baz)


    def test_constructWithPatches(self):
        """
        Constructing a L{MonkeyPatcher} with patches should add all of the
        given patches to the patch list.
        """
        patcher = MonkeyPatcher((self.testObject, 'foo', 'haha'),
                                (self.testObject, 'bar', 'hehe'))
        patcher.patch()
        self.assertEquals('haha', self.testObject.foo)
        self.assertEquals('hehe', self.testObject.bar)
        self.assertEquals(self.originalObject.baz, self.testObject.baz)


    def test_patchExisting(self):
        """
        Patching an attribute that exists sets it to the value defined in the
        patch.
        """
        self.monkeyPatcher.addPatch(self.testObject, 'foo', 'haha')
        self.monkeyPatcher.patch()
        self.assertEquals(self.testObject.foo, 'haha')


    def test_patchAlreadyPatched(self):
        """
        Adding a patch for an object and attribute that already have a patch
        overrides the existing patch.
        """
        self.monkeyPatcher.addPatch(self.testObject, 'foo', 'blah')
        self.monkeyPatcher.addPatch(self.testObject, 'foo', 'BLAH')
        self.monkeyPatcher.patch()
        self.assertEquals(self.testObject.foo, 'BLAH')
        self.monkeyPatcher.restore()
        self.assertEquals(self.testObject.foo, self.originalObject.foo)


    def test_restoreTwiceIsANoOp(self):
        """
        Restoring an already-restored monkey patch is a no-op.
        """
        self.monkeyPatcher.addPatch(self.testObject, 'foo', 'blah')
        self.monkeyPatcher.patch()
        self.monkeyPatcher.restore()
        self.assertEquals(self.testObject.foo, self.originalObject.foo)
        self.monkeyPatcher.restore()
        self.assertEquals(self.testObject.foo, self.originalObject.foo)


    def test_runWithPatchesDecoration(self):
        """
        runWithPatches should run the given callable, passing in all arguments
        and keyword arguments, and return the return value of the callable.
        """
        log = []

        def f(a, b, c=None):
            log.append((a, b, c))
            return 'foo'

        result = self.monkeyPatcher.runWithPatches(f, 1, 2, c=10)
        self.assertEquals('foo', result)
        self.assertEquals([(1, 2, 10)], log)


    def test_repeatedRunWithPatches(self):
        """
        We should be able to call the same function with runWithPatches more
        than once. All patches should apply for each call.
        """
        def f():
            return (self.testObject.foo, self.testObject.bar,
                    self.testObject.baz)

        self.monkeyPatcher.addPatch(self.testObject, 'foo', 'haha')
        result = self.monkeyPatcher.runWithPatches(f)
        self.assertEquals(
            ('haha', self.originalObject.bar, self.originalObject.baz), result)
        result = self.monkeyPatcher.runWithPatches(f)
        self.assertEquals(
            ('haha', self.originalObject.bar, self.originalObject.baz),
            result)


    def test_runWithPatchesRestores(self):
        """
        C{runWithPatches} should restore the original values after the function
        has executed.
        """
        self.monkeyPatcher.addPatch(self.testObject, 'foo', 'haha')
        self.assertEquals(self.originalObject.foo, self.testObject.foo)
        self.monkeyPatcher.runWithPatches(lambda: None)
        self.assertEquals(self.originalObject.foo, self.testObject.foo)


    def test_runWithPatchesRestoresOnException(self):
        """
        Test runWithPatches restores the original values even when the function
        raises an exception.
        """
        def _():
            self.assertEquals(self.testObject.foo, 'haha')
            self.assertEquals(self.testObject.bar, 'blahblah')
            raise RuntimeError, "Something went wrong!"

        self.monkeyPatcher.addPatch(self.testObject, 'foo', 'haha')
        self.monkeyPatcher.addPatch(self.testObject, 'bar', 'blahblah')

        self.assertRaises(RuntimeError, self.monkeyPatcher.runWithPatches, _)
        self.assertEquals(self.testObject.foo, self.originalObject.foo)
        self.assertEquals(self.testObject.bar, self.originalObject.bar)


    def test_attributeNotPresent(self):
        """
        L{MonkeyPatcher.patch} should be able to patch an attribute not present
        in the class, and L{MonkeyPatcher.restore} should delete it afterwards.
        """
        self.monkeyPatcher.addPatch(self.testObject, 'egg', 'spam')
        self.monkeyPatcher.patch()
        self.assertEquals(self.testObject.egg, 'spam')
        self.monkeyPatcher.restore()
        self.assertRaises(AttributeError, getattr, self.testObject, "egg")


    def test_patchToNotPresentAttribute(self):
        """
        When L{MonkeyPatcher.NOT_PRESENT} is passed as value to
        L{MonkeyPatcher.patch}, the attribute of the object is deleted.
        """
        self.monkeyPatcher.addPatch(self.testObject, 'foo',
                                    self.monkeyPatcher.NOT_PRESENT)
        self.monkeyPatcher.patch()
        self.assertRaises(AttributeError, getattr, self.testObject, "foo")
        self.monkeyPatcher.restore()
        self.assertEquals(self.testObject.foo, self.originalObject.foo)


    def test_patchNotNotPresentAttributeAlreadyNotPresent(self):
        """
        If L{MonkeyPatcher.NOT_PRESENT} is passed as value to
        L{MonkeyPatcher.patch} but the attribute doesn't exist, it doesn't
        break patch and restore.
        """
        self.monkeyPatcher.addPatch(self.testObject, 'egg',
                                    self.monkeyPatcher.NOT_PRESENT)
        self.monkeyPatcher.patch()
        self.assertRaises(AttributeError, getattr, self.testObject, "egg")
        self.monkeyPatcher.restore()
        self.assertRaises(AttributeError, getattr, self.testObject, "egg")
