# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


import sys, os
import types

from twisted.trial import unittest
from twisted.python import rebuild

import crash_test_dummy
f = crash_test_dummy.foo

class Foo: pass
class Bar(Foo): pass
class Baz(object): pass
class Buz(Bar, Baz): pass

class HashRaisesRuntimeError:
    """
    Things that don't hash (raise an Exception) should be ignored by the
    rebuilder.

    @ivar hashCalled: C{bool} set to True when __hash__ is called.
    """
    def __init__(self):
        self.hashCalled = False

    def __hash__(self):
        self.hashCalled = True
        raise RuntimeError('not a TypeError!')



unhashableObject = None # set in test_hashException



class RebuildTests(unittest.TestCase):
    """
    Simple testcase for rebuilding, to at least exercise the code.
    """
    def setUp(self):
        self.libPath = self.mktemp()
        os.mkdir(self.libPath)
        self.fakelibPath = os.path.join(self.libPath, 'twisted_rebuild_fakelib')
        os.mkdir(self.fakelibPath)
        file(os.path.join(self.fakelibPath, '__init__.py'), 'w').close()
        sys.path.insert(0, self.libPath)

    def tearDown(self):
        sys.path.remove(self.libPath)

    def testFileRebuild(self):
        from twisted.python.util import sibpath
        import shutil, time
        shutil.copyfile(sibpath(__file__, "myrebuilder1.py"),
                        os.path.join(self.fakelibPath, "myrebuilder.py"))
        from twisted_rebuild_fakelib import myrebuilder
        a = myrebuilder.A()
        try:
            object
        except NameError:
            pass
        else:
            from twisted.test import test_rebuild
            b = myrebuilder.B()
            class C(myrebuilder.B):
                pass
            test_rebuild.C = C
            C()
        i = myrebuilder.Inherit()
        self.assertEqual(a.a(), 'a')
        # necessary because the file has not "changed" if a second has not gone
        # by in unix.  This sucks, but it's not often that you'll be doing more
        # than one reload per second.
        time.sleep(1.1)
        shutil.copyfile(sibpath(__file__, "myrebuilder2.py"),
                        os.path.join(self.fakelibPath, "myrebuilder.py"))
        rebuild.rebuild(myrebuilder)
        try:
            object
        except NameError:
            pass
        else:
            b2 = myrebuilder.B()
            self.assertEqual(b2.b(), 'c')
            self.assertEqual(b.b(), 'c')
        self.assertEqual(i.a(), 'd')
        self.assertEqual(a.a(), 'b')
        # more work to be done on new-style classes
        # self.assertEqual(c.b(), 'c')

    def testRebuild(self):
        """
        Rebuilding an unchanged module.
        """
        # This test would actually pass if rebuild was a no-op, but it
        # ensures rebuild doesn't break stuff while being a less
        # complex test than testFileRebuild.

        x = crash_test_dummy.X('a')

        rebuild.rebuild(crash_test_dummy, doLog=False)
        # Instance rebuilding is triggered by attribute access.
        x.do()
        self.failUnlessIdentical(x.__class__, crash_test_dummy.X)

        self.failUnlessIdentical(f, crash_test_dummy.foo)

    def testComponentInteraction(self):
        x = crash_test_dummy.XComponent()
        x.setAdapter(crash_test_dummy.IX, crash_test_dummy.XA)
        x.getComponent(crash_test_dummy.IX)
        rebuild.rebuild(crash_test_dummy, 0)
        newComponent = x.getComponent(crash_test_dummy.IX)

        newComponent.method()

        self.assertEqual(newComponent.__class__, crash_test_dummy.XA)

        # Test that a duplicate registerAdapter is not allowed
        from twisted.python import components
        self.failUnlessRaises(ValueError, components.registerAdapter,
                              crash_test_dummy.XA, crash_test_dummy.X,
                              crash_test_dummy.IX)

    def testUpdateInstance(self):
        global Foo, Buz

        b = Buz()

        class Foo:
            def foo(self):
                pass
        class Buz(Bar, Baz):
            x = 10

        rebuild.updateInstance(b)
        assert hasattr(b, 'foo'), "Missing method on rebuilt instance"
        assert hasattr(b, 'x'), "Missing class attribute on rebuilt instance"

    def testBananaInteraction(self):
        from twisted.python import rebuild
        from twisted.spread import banana
        rebuild.latestClass(banana.Banana)


    def test_hashException(self):
        """
        Rebuilding something that has a __hash__ that raises a non-TypeError
        shouldn't cause rebuild to die.
        """
        global unhashableObject
        unhashableObject = HashRaisesRuntimeError()
        def _cleanup():
            global unhashableObject
            unhashableObject = None
        self.addCleanup(_cleanup)
        rebuild.rebuild(rebuild)
        self.assertEqual(unhashableObject.hashCalled, True)



class NewStyleTests(unittest.TestCase):
    """
    Tests for rebuilding new-style classes of various sorts.
    """
    def setUp(self):
        self.m = types.ModuleType('whipping')
        sys.modules['whipping'] = self.m


    def tearDown(self):
        del sys.modules['whipping']
        del self.m


    def test_slots(self):
        """
        Try to rebuild a new style class with slots defined.
        """
        classDefinition = (
            "class SlottedClass(object):\n"
            "    __slots__ = ['a']\n")

        exec classDefinition in self.m.__dict__
        inst = self.m.SlottedClass()
        inst.a = 7
        exec classDefinition in self.m.__dict__
        rebuild.updateInstance(inst)
        self.assertEqual(inst.a, 7)
        self.assertIdentical(type(inst), self.m.SlottedClass)

    if sys.version_info < (2, 6):
        test_slots.skip = "__class__ assignment for class with slots is only available starting Python 2.6"


    def test_errorSlots(self):
        """
        Try to rebuild a new style class with slots defined: this should fail.
        """
        classDefinition = (
            "class SlottedClass(object):\n"
            "    __slots__ = ['a']\n")

        exec classDefinition in self.m.__dict__
        inst = self.m.SlottedClass()
        inst.a = 7
        exec classDefinition in self.m.__dict__
        self.assertRaises(rebuild.RebuildError, rebuild.updateInstance, inst)

    if sys.version_info >= (2, 6):
        test_errorSlots.skip = "__class__ assignment for class with slots should work starting Python 2.6"


    def test_typeSubclass(self):
        """
        Try to rebuild a base type subclass.
        """
        classDefinition = (
            "class ListSubclass(list):\n"
            "    pass\n")

        exec classDefinition in self.m.__dict__
        inst = self.m.ListSubclass()
        inst.append(2)
        exec classDefinition in self.m.__dict__
        rebuild.updateInstance(inst)
        self.assertEqual(inst[0], 2)
        self.assertIdentical(type(inst), self.m.ListSubclass)


    def test_instanceSlots(self):
        """
        Test that when rebuilding an instance with a __slots__ attribute, it
        fails accurately instead of giving a L{rebuild.RebuildError}.
        """
        classDefinition = (
            "class NotSlottedClass(object):\n"
            "    pass\n")

        exec classDefinition in self.m.__dict__
        inst = self.m.NotSlottedClass()
        inst.__slots__ = ['a']
        classDefinition = (
            "class NotSlottedClass:\n"
            "    pass\n")
        exec classDefinition in self.m.__dict__
        # Moving from new-style class to old-style should fail.
        self.assertRaises(TypeError, rebuild.updateInstance, inst)

