from twisted.trial import unittest, runner

class Foo(unittest.TestCase):
    def test_foo(self):
        pass


def test_suite():
    ts = runner.TestSuite()
    ts.name = "MyCustomSuite"
    return ts
