
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

"""
Test cases for explorer
"""

from pyunit import unittest

from twisted.python import explorer

class ObjectBrowserTestCase(unittest.TestCase):
    def setUp(self):
        class Foo:
            x=2
            def bar(self, a, b, c=3):
                return a+b-c
        self.Foo = Foo
        self.ob = explorer.ObjectBrowser(Foo)

    def testCode(self):
        assert self.ob.code('x') == 2, "something's wrong."

        self.ob.code('x=1')
        self.ob.code('def baz(self): return "I am foo"')
        assert self.Foo.x == 1,                "code('x=1') failed."
        assert self.Foo().baz() == "I am foo", "code('def baz(self): return \"I am foo\"' failed."

    def testMove(self):
        class Bar: pass
        self.ob.move(Bar)
        assert self.ob.ns == Bar, "move() failed."

    def testGetAttrs(self):
        assert self.ob.getAttrs() == ['__doc__', '__module__', 'bar', 'x'], "getAttrs() failed."

    def testCallMethod(self):
        self.ob.move(self.Foo())
        assert self.ob.callMeth('bar', 1, 2) == 0, "calling method 'bar' failed."


class SecureObjectBrowserTestCase(unittest.TestCase):
    def setUp(self):
        class Foo:
            pass

        self.Foo = Foo
        self.ob = explorer.SecureObjectBrowser(Foo)

    def testCode(self):
        try:
            self.ob.code('print 1')
        except AssertionError:
            pass
        else:
            assert 0, "Hey, code should've failed."

testCases = [ObjectBrowserTestCase, SecureObjectBrowserTestCase]
