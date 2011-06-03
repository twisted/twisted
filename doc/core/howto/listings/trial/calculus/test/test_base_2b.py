from calculus.base_2 import Calculation
from twisted.trial import unittest



class CalculationTestCase(unittest.TestCase):
    def setUp(self):
        self.calc = Calculation()


    def _test(self, operation, a, b, expected):
        result = operation(a, b)
        self.assertEqual(result, expected)


    def test_add(self):
        self._test(self.calc.add, 3, 8, 11)


    def test_subtract(self):
        self._test(self.calc.subtract, 7, 3, 4)


    def test_multiply(self):
        self._test(self.calc.multiply, 6, 9, 54)


    def test_divide(self):
        self._test(self.calc.divide, 12, 5, 2)
