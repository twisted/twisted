# -*- test-case-name: twisted.trial.test.test_trial -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from __future__ import nested_scopes

__version__ = "$Revision: 1.17 $"[11:-2]

from twisted.trial.reporter import SKIP, EXPECTED_FAILURE, FAILURE, ERROR, UNEXPECTED_SUCCESS, SUCCESS
from twisted.python import reflect, failure, log, procutils, util as pyutil, compat
from twisted.python.runtime import platformType
from twisted.internet import defer, reactor, protocol, error, threads
from twisted.protocols import loopback
from twisted.trial import unittest, reporter, util, runner, itrial
from twisted.trial.test import trialtest1, pyunit, trialtest3, trialtest4, common

# this is ok, the module has been designed for this usage
from twisted.trial.assertions import *

from pprint import pprint
import sys, os, os.path as osp, time, warnings
from os.path import join as opj
import cPickle as pickle
from cStringIO import StringIO

    
class LogObserver:
    channels = compat.adict(
        foobar = True
    )
    def __init__(self, outputter=None):
        self.outputter = outputter
        if outputter is None:
            self.outputter = lambda events, k: pyutil.println(''.join(events[k]))

    def setOutputter(self, f):
        if not callable(f):
            raise TypeError, "argument to setOutputter must be a callable object"
        self.outputter = f

    def install(self):
        log.addObserver(self)
        return self

    def remove(self):
        # hack to get around trial's brokeness
        if self in log.theLogPublisher.observers:
            log.removeObserver(self)

    def __call__(self, events):
        for k in events:
            if self.channels.get(k, None):
                #self.outputter(events, k)
                print repr(events)


statdatum = {"foo": "bar", "baz": "spam"}

class TestBenchmark(object):

    class Benchmark(common.BaseTest, unittest.TestCase):
        def benchmarkValues(self):
            self.methodCalled = True
            self.recordStat(statdatum)

    def testBenchmark(self):
        from twisted.trial.test.common import BogusReporter
        suite = runner.TestSuite(BogusReporter(), util._Janitor(), benchmark=True)
        suite.addTestClass(self.Benchmark)
        suite.run()

        stats = pickle.load(file('test.stats', 'rb'))
        failUnlessEqual(stats, {itrial.IFQMethodName(self.Benchmark.benchmarkValues): statdatum})

    def tearDownClass(self):
        # this is nasty, but Benchmark tests change global state by
        # deregistering adapters
        from twisted.trial import registerAdapter
        for a, o, i in [(None, itrial.ITestCaseFactory, itrial.ITestRunner),
                        (runner.TestCaseRunner, itrial.ITestCaseFactory, itrial.ITestRunner)]:
            registerAdapter(a, o, i)


class Benchmark(common.RegistryBaseMixin, unittest.TestCase):
    def testBenchmark(self):
        # this is side-effecty and awful, for details, take a look at the
        # suite property of common.RegistryBaseMixin 
        self._getSuite(newSuite=True, benchmark=True)
        self.suite.addTestClass(TestBenchmark.Benchmark)
        self.suite.run()
        stats = pickle.load(file('test.stats', 'rb'))
        failUnlessEqual(stats, {itrial.IFQMethodName(TestBenchmark.Benchmark.benchmarkValues): statdatum})


allMethods = ('setUpClass', 'setUp', 'tearDown', 'tearDownClass', 'method')

class FunctionalTest(common.RegistryBaseMixin, unittest.TestCase):
    """
    """
    cpp = None

    tci = property(lambda self: self.suite.children[0].testCaseInstance)
    tm = property(lambda self: self.suite.children[0].children[0])
    stdio = property(lambda self: self.tm.stderr + self.tm.stdout)

    def assertMethodsCalled(self, *methNames):
        for name in methNames:
            assertEqual(getattr(self.tci, "%sCalled" % name), True, '%s not called' % (name,))
    
    def assertMethodsNotCalled(self, *methNames):
        for name in methNames:
            assertEqual(getattr(self.tci, "%sCalled" % name), False, '%s not called' % (name,))

    def testBrokenSetUp(self):
        self.suite.addTestClass(trialtest1.TestFailureInSetUp)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'setUp')
        self.assertMethodsCalled('setUpClass', 'setUp', 'tearDownClass')
        self.assertMethodsNotCalled('method', 'tearDown')
        assert_(self.tm.errors)
        assert_(isinstance(self.tm.errors[0].value, trialtest1.FoolishError))

    def testBrokenTearDown(self):
        self.suite.addTestClass(trialtest1.TestFailureInTearDown)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'tearDown')
        self.assertMethodsCalled(*allMethods)
        assert_(self.tm.errors)
        assert_(isinstance(self.tm.errors[0].value, trialtest1.FoolishError))

    def testBrokenSetUpClass(self):
        self.suite.addTestClass(trialtest1.TestFailureInSetUpClass)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'setUpClass')
        self.assertMethodsCalled('setUpClass')
        self.assertMethodsNotCalled(*allMethods[1:])
        assert_(self.tm.errors)

    def testBrokenTearDownClass(self):
        self.suite.addTestClass(trialtest1.TestFailureInTearDownClass)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'tearDownClass')
        self.assertMethodsCalled(*allMethods)
#:        assert_(self.tm.errors)

#:    testBrokenTearDownClass.todo = "should tearDownClass failure fail the test method?"


    def testHiddenException(self):
        self.suite.addMethod(trialtest1.DemoTest.testHiddenException)
        self.suite.run()
        assertSubstring(trialtest1.HIDDEN_EXCEPTION_MSG, self.reporter.out)
        self.assertMethodsCalled(*allMethods)

    def testLeftoverSockets(self):
        self.suite.addMethod(trialtest1.SocketOpenTest.test_socketsLeftOpen)
        self.suite.run()
        assert_(self.reporter.cleanerrs)
        assert_(isinstance(self.reporter.cleanerrs[0].value, util.DirtyReactorWarning))
        self.assertMethodsCalled(*allMethods)

    def testLeftoverPendingCalls(self):
        self.suite.addMethod(trialtest1.ReactorCleanupTests.test_leftoverPendingCalls)
        self.suite.run()
        assert_(self.tm.errors)
        assert_(isinstance(self.tm.errors[0].value, util.PendingTimedCallsError))
        self.assertMethodsCalled(*allMethods)

    def testPyUnitSupport(self):
        self.suite.addTestClass(pyunit.PyUnitTest)
        self.suite.run()
        self.assertMethodsCalled(*allMethods)

    def testClassTimeoutAttribute(self):
        """test to make sure that class-attribute timeout works"""
        self.suite.addTestClass(trialtest3.TestClassTimeoutAttribute)
        self.suite.run()
        assert_(self.tm.errors)
        assert_(isinstance(self.tm.errors[0].value, trialtest3.ClassTimeout))

    def testCorrectNumberTestReporting(self):
        """make sure trial reports the correct number of tests run (issue 770)"""
        self.suite.addModule(trialtest4)
        self.suite.run()
        assertSubstring("Ran 1 tests in", self.reporter.out)

    def testSuppressMethod(self):
        """please ignore the following warnings, we're testing method-level warning suppression"""
        self.suite.addMethod(trialtest3.TestSuppression.testSuppressMethod)
        self.suite.run()
        assertNotSubstring(trialtest3.METHOD_WARNING_MSG, self.stdio)
        assertSubstring(trialtest3.CLASS_WARNING_MSG, self.stdio)
        assertSubstring(trialtest3.MODULE_WARNING_MSG, self.stdio)

    def testSuppressClass(self):
        """please ignore the following warnings, we're testing class-level warning suppression"""
        self.suite.addMethod(trialtest3.TestSuppression.testSuppressClass)
        self.suite.run()
        assertSubstring(trialtest3.METHOD_WARNING_MSG, self.stdio)
        assertNotSubstring(trialtest3.CLASS_WARNING_MSG, self.stdio)
        assertSubstring(trialtest3.MODULE_WARNING_MSG, self.stdio)

    def testSuppressModule(self):
        """please ignore the following warnings, we're testing module-level warning suppression"""
        self.suite.addMethod(trialtest3.TestSuppression2.testSuppressModule)
        self.suite.run()
        assertSubstring(trialtest3.METHOD_WARNING_MSG, self.stdio)
        assertSubstring(trialtest3.CLASS_WARNING_MSG, self.stdio)
        assertNotSubstring(trialtest3.MODULE_WARNING_MSG, self.stdio)

    def testOverrideSuppressClass(self):
        """please ignore the following warnings, we're testing override of warning suppression"""
        self.suite.addMethod(trialtest3.TestSuppression.testOverrideSuppressClass)
        self.suite.run()
        assertSubstring(trialtest3.CLASS_WARNING_MSG, self.stdio)
        assertSubstring(trialtest3.MODULE_WARNING_MSG, self.stdio)
        assertSubstring(trialtest3.METHOD_WARNING_MSG, self.stdio)

    def testImportErrorsFailRun(self):
        self.suite.addModule('twisted.trial.test.importErrors')
        self.suite.run()
        assertEqual(itrial.ITestStats(self.suite).allPassed, False)
        self.failIfImportErrors = False

        
FunctionalTest.timeout = 30.0
