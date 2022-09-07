# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Sample test cases defined using the standard library L{unittest.TestCase}
class which are used as data by test cases which are actually part of the
trial test suite to verify handling of handling of such cases.
"""

import unittest


class PyUnitTest(unittest.TestCase):
    def test_pass(self):
        """
        A passing test.
        """

    def test_error(self):
        """
        A test which raises an exception to cause an error.
        """
        raise Exception("pyunit error")

    def test_fail(self):
        """
        A test which uses L{unittest.TestCase.fail} to cause a failure.
        """
        self.fail("pyunit failure")

    @unittest.skip("pyunit skip")
    def test_skip(self):
        """
        A test which uses the L{unittest.skip} decorator to cause a skip.
        """


class BrokenRunInfrastructure(unittest.TestCase):
    """
    A test suite that is broken at the level of integration between
    L{TestCase.run} and the results object.
    """

    def run(self, result):
        """
        Override the normal C{run} behavior to pass the result object
        along to the test method.  Each test method needs the result object so
        that it can implement its particular kind of brokenness.
        """
        return getattr(self, self._testMethodName)(result)

    def test_addSuccess(self, result):
        """
        Violate the L{TestResult.addSuccess} interface.
        """

        class NonStringId:
            def id(self) -> object:
                return object()

        result.addSuccess(NonStringId())
