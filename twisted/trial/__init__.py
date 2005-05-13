# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

"""Unit testing framework."""

tbformat = 'plain'

from twisted.python import components
try:
    from zope.interface import interface, declarations
    from zope.interface.adapter import AdapterRegistry
except ImportError:
    raise ImportError, "you need zope.interface installed (http://zope.org/Products/ZopeInterface/)"

#XXX: Having this be here is pretty damn lame, but it's better than the whole
# mess with adapter registries that was here before.
benchmarking = False

def makeTestRunner(orig):
    if benchmarking:
        return runner.BenchmarkCaseRunner(orig)
    else:
        return runner.TestCaseRunner(orig)

def makeTestMethod(orig):
    if benchmarking:
        return runner.BenchmarkMethod(orig)
    else:
        return runner.TestMethod(orig)
    
def _setUpAdapters():
    from twisted.spread import jelly
    from twisted.python import failure
    # sibling imports
    import types
    import reporter, runner, itrial, adapters, remote
    import tdoctest, doctest
    
    for a, o, i in [

# ---- ITestRunner and ITestMethod adapters -----------
(makeTestRunner, itrial.ITestCaseFactory, itrial.ITestRunner),
(runner.TestModuleRunner, types.ModuleType, itrial.ITestRunner),
(runner.PyUnitTestCaseRunner, itrial.IPyUnitTCFactory, itrial.ITestRunner),
(runner.TestCaseMethodRunner, types.MethodType, itrial.ITestRunner),
(makeTestMethod, types.MethodType, itrial.ITestMethod),

# ---- Doctest support --------------------------------
(tdoctest.DocTestRunnerToITestMethod, tdoctest.DocTestRunner, itrial.ITestMethod),
(tdoctest.DocTestRunner, doctest.DocTest, itrial.ITestRunner),

# XXX: i'm not happy about this association
(tdoctest.ModuleDocTestsRunner, types.ListType, itrial.ITestRunner),


# ---- Error Reporting and Failure formatting ----------
(adapters.formatFailureTraceback, failure.Failure, itrial.IFormattedFailure),
(adapters.formatMultipleFailureTracebacks, types.ListType, itrial.IFormattedFailure),
(adapters.formatMultipleFailureTracebacks, types.TupleType, itrial.IFormattedFailure),
(adapters.formatTestMethodFailures, itrial.ITestMethod, itrial.IFormattedFailure),
(adapters.formatError, itrial.ITestMethod, itrial.IErrorReport),
(adapters.formatImportError, types.TupleType, itrial.IImportErrorReport),
(adapters.formatDoctestError, itrial.IDocTestMethod, itrial.IErrorReport),

# ---- ITestStats  ------------------------------------
(reporter.TestStats, itrial.ITestSuite, itrial.ITestStats),
(reporter.TestStats, runner.TestModuleRunner, itrial.ITestStats),
(reporter.TestStats, tdoctest.ModuleDocTestsRunner, itrial.ITestStats),
(reporter.DocTestRunnerStats, tdoctest.DocTestRunner, itrial.ITestStats),
(reporter.TestCaseStats, runner.TestCaseRunner, itrial.ITestStats),
(reporter.TestCaseStats, runner.TestCaseMethodRunner, itrial.ITestStats),
(reporter.TestCaseStats, runner.PyUnitTestCaseRunner, itrial.ITestStats),

# ---- Magic Attribute Adapters -----------------------
(adapters.TupleTodo, types.TupleType, itrial.ITodo),
(adapters.StringTodo, types.StringType, itrial.ITodo),
(adapters.TodoBase, types.NoneType, itrial.ITodo),
#(runner.UserMethodWrapper, types.MethodType, itrial.IUserMethod),
(remote.JellyableTestMethod, itrial.ITestMethod, jelly.IJellyable)]:

        components.registerAdapter(a, o, i)

_setUpAdapters()

