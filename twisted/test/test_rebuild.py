# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
import new

from twisted.trial import unittest
from twisted.python import rebuild

import crash_test_dummy
from twisted.web import server
f = crash_test_dummy.foo

if sys.version_info >= (2, 2, 0):
    class Foo: pass
    class Bar(Foo): pass
    class Baz(object): pass
    class Buz(Bar, Baz): pass

class RebuildTestCase(unittest.TestCase):
    """Simple testcase for rebuilding, to at least exercise the code.
    """
    def testFileRebuild(self):
        from twisted.python.rebuild import rebuild
        from twisted.python.util import sibpath
        import shutil, time
        shutil.copyfile(sibpath(__file__, "myrebuilder1.py"),
                        sibpath(__file__, "myrebuilder.py"))
        from twisted.test import myrebuilder
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
            c = C()
        i = myrebuilder.Inherit()
        self.assertEquals(a.a(), 'a')
        # necessary because the file has not "changed" if a second has not gone
        # by in unix.  This sucks, but it's not often that you'll be doing more
        # than one reload per second.
        time.sleep(1.1)
        shutil.copyfile(sibpath(__file__, "myrebuilder2.py"),
                        sibpath(__file__, "myrebuilder.py"))
        rebuild(myrebuilder)
        try:
            object
        except NameError:
            pass
        else:
            b2 = myrebuilder.B()
            self.assertEquals(b2.b(), 'c')
            self.assertEquals(b.b(), 'c')
        self.assertEquals(i.a(), 'd')
        self.assertEquals(a.a(), 'b')
        # more work to be done on new-style classes
        # self.assertEquals(c.b(), 'c')

    def testRebuild(self):
        """Rebuilding an unchanged module."""
        # This test would actually pass if rebuild was a no-op, but it
        # ensures rebuild doesn't break stuff while being a less
        # complex test than testFileRebuild.
        
        x = crash_test_dummy.X('a')

        rebuild.rebuild(crash_test_dummy, doLog=False)
        # Instance rebuilding is triggered by attribute access.
        x.do()
        self.failUnlessIdentical(x.__class__, crash_test_dummy.X)

        # Just for kicks?
        rebuild.rebuild(server, doLog=False)
        self.failUnlessIdentical(f, crash_test_dummy.foo)

    def testComponentInteraction(self):
        x = crash_test_dummy.XComponent()
        x.setAdapter(crash_test_dummy.IX, crash_test_dummy.XA)
        oldComponent = x.getComponent(crash_test_dummy.IX)
        rebuild.rebuild(crash_test_dummy, 0)
        newComponent = x.getComponent(crash_test_dummy.IX)

        newComponent.method()

        self.assertEquals(newComponent.__class__, crash_test_dummy.XA)

        # Test that a duplicate registerAdapter is not allowed
        from twisted.python import components
        self.failUnlessRaises(ValueError, components.registerAdapter,
                              crash_test_dummy.XA, crash_test_dummy.X,
                              crash_test_dummy.IX)

    if sys.version_info >= (2, 2, 0):
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

class NewStyleTestCase(unittest.TestCase):
    todo = """New Style classes are poorly supported"""

    def setUp(self):
        self.m = new.module('whipping')
        sys.modules['whipping'] = self.m
    
    def tearDown(self):
        del sys.modules['whipping']
        del self.m
    
    def testSlots(self):
        exec "class SlottedClass(object): __slots__ = 'a'," in self.m.__dict__
        rebuild.updateInstance(self.m.SlottedClass())

    def testTypeSubclass(self):
        exec "class ListSubclass(list): pass" in self.m.__dict__
        rebuild.updateInstance(self.m.ListSubclass())
