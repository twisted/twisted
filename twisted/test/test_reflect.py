
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
Test cases for twisted.reflect module.
"""

# Twisted Imports
from twisted.trial import unittest
from twisted.python import reflect


class SettableTest(unittest.TestCase):
    def setUp(self):
        self.setter = reflect.Settable()

    def tearDown(self):
        del self.setter

    def testSet(self):
        self.setter(a=1, b=2)
        self.failUnlessEqual(self.setter.a, 1)
        self.failUnlessEqual(self.setter.b, 2)


class AccessorTester(reflect.Accessor):
    def set_x(self, x):
        self.y = x
        self.reallySet('x',x)

    def get_z(self):
        self.q = 1
        return 1

    def del_z(self):
        self.reallyDel("q")


class AccessorTest(unittest.TestCase):
    def setUp(self):
        self.tester = AccessorTester()

    def testSet(self):
        self.tester.x = 1
        self.failUnlessEqual(self.tester.x, 1)
        self.failUnlessEqual(self.tester.y, 1)

    def testGet(self):
        self.failUnlessEqual(self.tester.z, 1)
        self.failUnlessEqual(self.tester.q, 1)

    def testDel(self):
        self.tester.z
        self.failUnlessEqual(self.tester.q, 1)
        del self.tester.z
        self.failUnlessEqual(hasattr(self.tester, "q"), 0)
        self.tester.x = 1
        del self.tester.x
        self.failUnlessEqual(hasattr(self.tester, "x"), 0)


class LookupsTestCase(unittest.TestCase):
    """Test lookup methods."""

    def testClassLookup(self):
        self.assertEquals(reflect.namedClass("twisted.python.reflect.Summer"), reflect.Summer)

    def testModuleLookup(self):
        self.assertEquals(reflect.namedModule("twisted.python.reflect"), reflect)

class LookupsTestCaseII(unittest.TestCase):
    def testPackageLookup(self):
        import twisted.python
        self.failUnlessIdentical(reflect.namedAny("twisted.python"),
                                 twisted.python)

    def testModuleLookup(self):
        self.failUnlessIdentical(reflect.namedAny("twisted.python.reflect"),
                                 reflect)

    def testClassLookup(self):
        self.failUnlessIdentical(reflect.namedAny("twisted.python."
                                                  "reflect.Summer"),
                                 reflect.Summer)

    def testAttributeLookup(self):
        # Why does Identical break down here?
        self.failUnlessEqual(reflect.namedAny("twisted.python."
                                              "reflect.Summer.reallySet"),
                             reflect.Summer.reallySet)

    def testSecondAttributeLookup(self):
        self.failUnlessIdentical(reflect.namedAny("twisted.python."
                                                  "reflect.Summer."
                                                  "reallySet.__doc__"),
                                 reflect.Summer.reallySet.__doc__)
