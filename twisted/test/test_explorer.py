"""
Test cases for explorer
"""

from pyunit import unittest

from twisted.python import explorer
from twisted.python import authenticator

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
        except authenticator.Unauthorized: pass
        else:
            raise AssertionError, "Hey, code should've failed."

testCases = [ObjectBrowserTestCase, SecureObjectBrowserTestCase]
