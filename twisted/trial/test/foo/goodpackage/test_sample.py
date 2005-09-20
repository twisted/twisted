"""This module is used by test_loader to test the Trial test loading
functionality. Do NOT change the number of tests in this module.  Do NOT change
the names the tests in this module.
"""

import unittest as pyunit
from twisted.trial import unittest

class FooTest(unittest.TestCase):
    def test_foo(self):
        pass

    def test_bar(self):
        pass


class PyunitTest(pyunit.TestCase):
    def test_foo(self):
        pass

    def test_bar(self):
        pass


class NotATest(object):
    def test_foo(self):
        pass


class AlphabetTest(unittest.TestCase):
    def test_a(self):
        pass

    def test_b(self):
        pass

    def test_c(self):
        pass


