# -*- test-case-name: calculus.test.test_base_3 -*-

class Calculation(object):

    def _robust_int(self, arg):
        try:
            return int(arg)
        except ValueError:
            raise TypeError("Couldn't coerce argument to integer: %s" % arg)

    def _make_ints(self, *args):
        return map(self._robust_int, args)

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
