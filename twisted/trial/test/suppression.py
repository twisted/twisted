# -*- test-case-name: twisted.trial.test.test_tests -*-

import warnings

from twisted.trial import unittest, util


""" test to make sure that warning supression works at the module, method, and
class levels
"""

METHOD_WARNING_MSG = "method warning message"
CLASS_WARNING_MSG = "class warning message"
MODULE_WARNING_MSG = "module warning message"

class MethodWarning(Warning):
    pass

class ClassWarning(Warning):
    pass

class ModuleWarning(Warning):
    pass

class EmitMixin:
    __counter = 0

    def _emit(self):
        warnings.warn(METHOD_WARNING_MSG + '_%s' % (EmitMixin.__counter), MethodWarning)
        warnings.warn(CLASS_WARNING_MSG + '_%s' % (EmitMixin.__counter), ClassWarning)
        warnings.warn(MODULE_WARNING_MSG + '_%s' % (EmitMixin.__counter), ModuleWarning)
        EmitMixin.__counter += 1


class TestSuppression(unittest.TestCase, EmitMixin):
    def testSuppressMethod(self):
        self._emit()
    testSuppressMethod.suppress = [util.suppress(message=METHOD_WARNING_MSG)]

    def testSuppressClass(self):
        self._emit()

    def testOverrideSuppressClass(self):
        self._emit()
    testOverrideSuppressClass.suppress = []

TestSuppression.suppress = [util.suppress(message=CLASS_WARNING_MSG)]
                            

class TestSuppression2(unittest.TestCase, EmitMixin):
    def testSuppressModule(self):
        self._emit()

suppress = [util.suppress(message=MODULE_WARNING_MSG)]


