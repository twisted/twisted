import unittest


class PyUnitTest(unittest.TestCase):
    def test_pass(self):
        pass

    def test_error(self):
        raise Exception("pyunit error")

    def test_fail(self):
        self.fail("pyunit failure")

    def test_skip(self):
        self.skip("pyunit skip")
