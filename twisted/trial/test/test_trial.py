# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

from __future__ import nested_scopes

__version__ = "$Revision: 1.17 $"[11:-2]

from twisted.trial.reporter import SKIP, EXPECTED_FAILURE, FAILURE, ERROR, UNEXPECTED_SUCCESS, SUCCESS
from twisted.python import reflect, failure, log, util as pyutil, compat
from twisted.python.runtime import platformType
from twisted.internet import defer, reactor, protocol, error, threads
from twisted.protocols import loopback
from twisted.trial import unittest, reporter, util, runner, itrial
from twisted.trial.test import erroneous, pyunit, timeoutAttr, suppression, numOfTests, common

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

class TestSkip(common.RegistryBaseMixin, unittest.TestCase):
    """
    Test that setUp is not run when class is set to skip
    """

    def testSkippedClasses(self):
        class SkipperTester(unittest.TestCase):

            skip = 'yes'

            errorStr = ''

            def setUpClass(self):
                '''
                The class is set to skip, this should not be run
                '''
                SkipperTester.errorStr += "setUpClass should be skipped because the class has skip = 'yes'\n"

            def tearDownClass(self):
                '''
                This method should also not run.
                '''
                SkipperTester.errorStr += "tearDownClass should be skipped because the class has skip = 'yes'\n"

            def testSkip(self):
                '''
                The class is set to skip, this should not be run
                '''
                SkipperTester.errorStr += "testSkip should be skipped because the class has skip = 'yes'\n"

        from twisted import trial
        from twisted.trial.test.common import BogusReporter

        suite = self._getSuite(newSuite=True, benchmark=False)
        suite.addTestClass(SkipperTester)
        suite.run()
        self.failIf(SkipperTester.errorStr, SkipperTester.errorStr)


class TestBenchmark(object):

    class Benchmark(common.BaseTest, unittest.TestCase):
        def benchmarkValues(self):
            self.methodCalled = True
            self.recordStat(statdatum)

    def testBenchmark(self):
        from twisted.trial.test.common import BogusReporter
        from twisted import trial
        
        suite = runner.TestSuite(BogusReporter(), util._Janitor(), benchmark=True)
        suite.addTestClass(self.Benchmark)
        suite.run()

        stats = pickle.load(file('test.stats', 'rb'))
        failUnlessEqual(stats, {reflect.qual(self.Benchmark.benchmarkValues): statdatum})



class Benchmark(common.RegistryBaseMixin, unittest.TestCase):
    def testBenchmark(self):
        from twisted import trial
        # this is side-effecty and awful, for details, take a look at the
        # suite property of common.RegistryBaseMixin 
        self._getSuite(newSuite=True, benchmark=True)
        self.suite.addTestClass(TestBenchmark.Benchmark)
        self.suite.run()

        # Sucks but less than before
        trial.benchmarking = False
        
        stats = pickle.load(file('test.stats', 'rb'))
        meth = TestBenchmark.Benchmark.benchmarkValues
        mod = inspect.getmodule(meth).__name__
        failUnlessEqual(stats, {mod: statdatum})


allMethods = ('setUpClass', 'setUp', 'tearDown', 'tearDownClass', 'method')

class FunctionalTest(common.RegistryBaseMixin, unittest.TestCase):
    """
    """
    cpp = None

    def assertMethodsCalled(self, *methNames):
        for name in methNames:
            assertEqual(getattr(self.tci, "%sCalled" % name), True, '%s not called' % (name,))
    
    def assertMethodsNotCalled(self, *methNames):
        for name in methNames:
            assertEqual(getattr(self.tci, "%sCalled" % name), False, '%s not called' % (name,))

    def testBrokenSetUp(self):
        self.suite.addTestClass(erroneous.TestFailureInSetUp)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'setUp')
        self.assertMethodsCalled('setUpClass', 'setUp', 'tearDownClass')
        self.assertMethodsNotCalled('method', 'tearDown')
        assert_(self.tm.errors)
        assert_(isinstance(self.tm.errors[0].value, erroneous.FoolishError))

    def testBrokenTearDown(self):
        self.suite.addTestClass(erroneous.TestFailureInTearDown)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'tearDown')
        self.assertMethodsCalled(*allMethods)
        assert_(self.tm.errors)
        assert_(isinstance(self.tm.errors[0].value, erroneous.FoolishError))

    def testBrokenSetUpClass(self):
        self.suite.addTestClass(erroneous.TestFailureInSetUpClass)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'setUpClass')
        self.assertMethodsCalled('setUpClass')
        self.assertMethodsNotCalled(*allMethods[1:])
        assert_(self.tm.errors)

    def testBrokenTearDownClass(self):
        self.suite.addTestClass(erroneous.TestFailureInTearDownClass)
        self.suite.run()
        imi = itrial.IMethodInfo(self.reporter.udeMethod)
        assertEqual(imi.name, 'tearDownClass')
        self.assertMethodsCalled(*allMethods)
#:        assert_(self.tm.errors)

#:    testBrokenTearDownClass.todo = "should tearDownClass failure fail the test method?"

    def testHiddenException(self):
        self.suite.addMethod(erroneous.DemoTest.testHiddenException)
        self.suite.run()
        assertSubstring(erroneous.HIDDEN_EXCEPTION_MSG, self.reporter.out)
        self.assertMethodsCalled(*allMethods)

    def testLeftoverSockets(self):
        self.suite.addMethod(erroneous.SocketOpenTest.test_socketsLeftOpen)
        self.suite.run()
        assert_(self.reporter.cleanerrs)
        assert_(isinstance(self.reporter.cleanerrs[0].value, util.DirtyReactorWarning))
        self.assertMethodsCalled(*allMethods)

    def testLeftoverPendingCalls(self):
        self.suite.addMethod(erroneous.ReactorCleanupTests.test_leftoverPendingCalls)
        self.suite.run()
        assert_(self.tm.errors)
        assert_(isinstance(self.tm.errors[0].value, util.PendingTimedCallsError))
        self.assertMethodsCalled(*allMethods)

    def testTimingOutDeferred(self):
        self.suite.addMethod(erroneous.TimingOutDeferred)
        self.suite.run()
        # assert_(self.tm.errors)
        # assert_(isinstance(self.tm.errors[0].value, defer.TimeoutError))
        # self.assertMethodsCalled(*allMethods)
        assertSubstring("FAILED (errors=1, successes=3)", self.reporter.out)

    def testPyUnitSupport(self):
        self.suite.addTestClass(pyunit.PyUnitTest)
        self.suite.run()
        self.assertMethodsCalled(*allMethods)

    def testClassTimeoutAttribute(self):
        """test to make sure that class-attribute timeout works"""
        self.suite.addTestClass(timeoutAttr.TestClassTimeoutAttribute)
        self.suite.run()
        assert_(self.tm.errors)
        self.tm.errors[0].trap(defer.TimeoutError)

    def testCorrectNumberTestReporting(self):
        """make sure trial reports the correct number of tests run (issue 770)"""
        self.suite.addModule(numOfTests)
        self.suite.run()
        assertSubstring("Ran 1 tests in", self.reporter.out)

    def testSuppressMethod(self):
        """please ignore the following warnings, we're testing method-level warning suppression"""
        self.suite.addMethod(suppression.TestSuppression.testSuppressMethod)
        self.suite.run()
        assertNotSubstring(suppression.METHOD_WARNING_MSG, self.stdio)
        assertSubstring(suppression.CLASS_WARNING_MSG, self.stdio)
        assertSubstring(suppression.MODULE_WARNING_MSG, self.stdio)

    def testSuppressClass(self):
        """please ignore the following warnings, we're testing class-level warning suppression"""
        self.suite.addMethod(suppression.TestSuppression.testSuppressClass)
        self.suite.run()
        assertSubstring(suppression.METHOD_WARNING_MSG, self.stdio)
        assertNotSubstring(suppression.CLASS_WARNING_MSG, self.stdio)
        assertSubstring(suppression.MODULE_WARNING_MSG, self.stdio)

    def testSuppressModule(self):
        """please ignore the following warnings, we're testing module-level warning suppression"""
        self.suite.addMethod(suppression.TestSuppression2.testSuppressModule)
        self.suite.run()
        assertSubstring(suppression.METHOD_WARNING_MSG, self.stdio)
        assertSubstring(suppression.CLASS_WARNING_MSG, self.stdio)
        assertNotSubstring(suppression.MODULE_WARNING_MSG, self.stdio)

    def testOverrideSuppressClass(self):
        """please ignore the following warnings, we're testing override of warning suppression"""
        self.suite.addMethod(suppression.TestSuppression.testOverrideSuppressClass)
        self.suite.run()
        assertSubstring(suppression.CLASS_WARNING_MSG, self.stdio)
        assertSubstring(suppression.MODULE_WARNING_MSG, self.stdio)
        assertSubstring(suppression.METHOD_WARNING_MSG, self.stdio)

    def testImportErrorsFailRun(self):
        self.failIfImportErrors = False
        modname = 'twisted.trial.test.importErrors'
        if modname in sys.modules:
            del sys.modules[modname]
        assert_(modname not in sys.modules)
        self.suite.addModule(modname)
        # in python-2.4, broken imports are not left in sys.modules
        #assert_(modname in sys.modules)
        self.suite.run()
        
        failIf(itrial.ITestStats(self.suite).allPassed)

        
FunctionalTest.timeout = 30.0
