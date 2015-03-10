from calculus.base_3 import Calculation
from twisted.trial import unittest



class CalculationTestCase(unittest.TestCase):
    def setUp(self):
        self.calc = Calculation()


    def _test(self, operation, a, b, expected):
        result = operation(a, b)
        self.assertEqual(result, expected)


    def _test_error(self, operation):
        self.assertRaises(TypeError, operation, "foo", 2)
        self.assertRaises(TypeError, operation, "bar", "egg")
        self.assertRaises(TypeError, operation, [3], [8, 2])
        self.assertRaises(TypeError, operation, {"e": 3}, {"r": "t"})


    def test_add(self):
        self._test(self.calc.add, 3, 8, 11)


    def test_subtract(self):
        self._test(self.calc.subtract, 7, 3, 4)


    def test_multiply(self):
        self._test(self.calc.multiply, 6, 9, 54)


    def test_divide(self):
        self._test(self.calc.divide, 12, 5, 2)


    def test_errorAdd(self):
        self._test_error(self.calc.add)


    def test_errorSubtract(self):
        self._test_error(self.calc.subtract)


    def test_errorMultiply(self):
        self._test_error(self.calc.multiply)


    def test_errorDivide(self):
        self._test_error(self.calc.divide)
