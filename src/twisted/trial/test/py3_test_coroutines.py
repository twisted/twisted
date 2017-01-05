# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.trial.unittest.TestCase} support for async test methods.
"""

from .. import reporter
from . import corotests, test_deferred



class CoroutineTests(test_deferred.DeferredTests):
    """
    Tests for L{twisted.trial.unittest.TestCase} support for async test
    methods.
    """

    def runTest(self, name):
        result = reporter.TestResult()
        corotests.CoroutineTests(name).run(result)
        return result


    def _notApplicable(self):
        raise NotImplementedError("Not applicable")

    _notApplicable.skip = "Not applicable"


    test_passGenerated = _notApplicable
    test_passInlineCallbacks = _notApplicable
