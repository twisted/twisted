"""
Test cases for twisted.reflect module.
"""

# Twisted Imports
from pyunit import unittest
from twisted.python import reflect

class SettableTest(unittest.TestCase):
    def setUp(self):
        self.setter = reflect.Settable()

    def tearDown(self):
        del self.setter

    def testSet(self):
        self.setter(a=1, b=2)
        assert self.setter.a == 1
        assert self.setter.b == 2


class AccessorTest(unittest.TestCase):
    def setUp(self):
        class Tester(reflect.Accessor):
            def set_x(self, x):
                self.y = x
                self.reallySet('x',x)
                
            def get_z(self):
                self.q = 1
                return 1

        self.tester = Tester()
        
    def testSet(self):
        self.tester.x = 1
        assert self.tester.x == 1
        assert self.tester.y == 1

    def testGet(self):
        assert self.tester.z == 1
        assert self.tester.q == 1

testCases = [SettableTest, AccessorTest]
