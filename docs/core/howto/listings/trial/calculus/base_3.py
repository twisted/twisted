# -*- test-case-name: calculus.test.test_base_3 -*-


class Calculation:
    def _make_ints(self, *args):
        try:
            return [int(arg) for arg in args]
        except ValueError:
            raise TypeError("Couldn't coerce arguments to integers: {}".format(*args))

    def add(self, a, b):
        a, b = self._make_ints(a, b)
        return a + b

    def subtract(self, a, b):
        a, b = self._make_ints(a, b)
        return a - b

    def multiply(self, a, b):
        a, b = self._make_ints(a, b)
        return a * b

    def divide(self, a, b):
        a, b = self._make_ints(a, b)
        return a // b
