
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for twisted.hook module.
"""

from twisted.python import hook
from twisted.trial import unittest

class BaseClass:
    """
    dummy class to help in testing.
    """
    def __init__(self):
        """
        dummy initializer
        """
        self.calledBasePre = 0
        self.calledBasePost = 0
        self.calledBase = 0

    def func(self, a, b):
        """
        dummy method
        """
        assert a == 1
        assert b == 2
        self.calledBase = self.calledBase + 1


class SubClass(BaseClass):
    """
    another dummy class
    """
    def __init__(self):
        """
        another dummy initializer
        """
        BaseClass.__init__(self)
        self.calledSubPre = 0
        self.calledSubPost = 0
        self.calledSub = 0

    def func(self, a, b):
        """
        another dummy function
        """
        assert a == 1
        assert b == 2
        BaseClass.func(self, a, b)
        self.calledSub = self.calledSub + 1

_clean_BaseClass = BaseClass.__dict__.copy()
_clean_SubClass = SubClass.__dict__.copy()

def basePre(base, a, b):
    """
    a pre-hook for the base class
    """
    base.calledBasePre = base.calledBasePre + 1

def basePost(base, a, b):
    """
    a post-hook for the base class
    """
    base.calledBasePost = base.calledBasePost + 1

def subPre(sub, a, b):
    """
    a pre-hook for the subclass
    """
    sub.calledSubPre = sub.calledSubPre + 1

def subPost(sub, a, b):
    """
    a post-hook for the subclass
    """
    sub.calledSubPost = sub.calledSubPost + 1

class HookTests(unittest.TestCase):
    """
    test case to make sure hooks are called
    """
    def setUp(self):
        """Make sure we have clean versions of our classes."""
        BaseClass.__dict__.clear()
        BaseClass.__dict__.update(_clean_BaseClass)
        SubClass.__dict__.clear()
        SubClass.__dict__.update(_clean_SubClass)

    def testBaseHook(self):
        """make sure that the base class's hook is called reliably
        """
        base = BaseClass()
        self.assertEqual(base.calledBase, 0)
        self.assertEqual(base.calledBasePre, 0)
        base.func(1,2)
        self.assertEqual(base.calledBase, 1)
        self.assertEqual(base.calledBasePre, 0)
        hook.addPre(BaseClass, "func", basePre)
        base.func(1, b=2)
        self.assertEqual(base.calledBase, 2)
        self.assertEqual(base.calledBasePre, 1)
        hook.addPost(BaseClass, "func", basePost)
        base.func(1, b=2)
        self.assertEqual(base.calledBasePost, 1)
        self.assertEqual(base.calledBase, 3)
        self.assertEqual(base.calledBasePre, 2)
        hook.removePre(BaseClass, "func", basePre)
        hook.removePost(BaseClass, "func", basePost)
        base.func(1, b=2)
        self.assertEqual(base.calledBasePost, 1)
        self.assertEqual(base.calledBase, 4)
        self.assertEqual(base.calledBasePre, 2)

    def testSubHook(self):
        """test interactions between base-class hooks and subclass hooks
        """
        sub = SubClass()
        self.assertEqual(sub.calledSub, 0)
        self.assertEqual(sub.calledBase, 0)
        sub.func(1, b=2)
        self.assertEqual(sub.calledSub, 1)
        self.assertEqual(sub.calledBase, 1)
        hook.addPre(SubClass, 'func', subPre)
        self.assertEqual(sub.calledSub, 1)
        self.assertEqual(sub.calledBase, 1)
        self.assertEqual(sub.calledSubPre, 0)
        self.assertEqual(sub.calledBasePre, 0)
        sub.func(1, b=2)
        self.assertEqual(sub.calledSub, 2)
        self.assertEqual(sub.calledBase, 2)
        self.assertEqual(sub.calledSubPre, 1)
        self.assertEqual(sub.calledBasePre, 0)
        # let the pain begin
        hook.addPre(BaseClass, 'func', basePre)
        BaseClass.func(sub, 1, b=2)
        # sub.func(1, b=2)
        self.assertEqual(sub.calledBase, 3)
        self.assertEqual(sub.calledBasePre, 1, str(sub.calledBasePre))
        sub.func(1, b=2)
        self.assertEqual(sub.calledBasePre, 2)
        self.assertEqual(sub.calledBase, 4)
        self.assertEqual(sub.calledSubPre, 2)
        self.assertEqual(sub.calledSub, 3)

testCases = [HookTests]
