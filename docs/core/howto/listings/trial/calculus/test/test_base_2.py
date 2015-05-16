from calculus.base_2 import Calculation
from twisted.trial import unittest



class CalculationTestCase(unittest.TestCase):

    def test_add(self):
        calc = Calculation()
        result = calc.add(3, 8)
        self.assertEqual(result, 11)


    def test_subtract(self):
        calc = Calculation()
        result = calc.subtract(7, 3)
        self.assertEqual(result, 4)


    def test_multiply(self):
        calc = Calculation()
        result = calc.multiply(12, 5)
        self.assertEqual(result, 60)


    def test_divide(self):
        calc = Calculation()
        result = calc.divide(12, 5)
        self.assertEqual(result, 2)
