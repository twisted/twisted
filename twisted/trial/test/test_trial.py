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

import inspect
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


class _StdioProxy(pyutil.SubclassableCStringIO):
    """Use me to store IO"""
    def __init__(self, original):
        super(_StdioProxy, self).__init__()
        self.original = original

    def __iter__(self):
        return self.original.__iter__()

    def write(self, s):
        super(_StdioProxy, self).write(s)
        return self.original.write(s)

    def writelines(self, list):
        super(_StdioProxy, self).writelines(list)
        return self.original.writelines(list)

    def flush(self):
        return self.original.flush()

    def next(self):
        return self.original.next()

    def close(self):
        return self.original.close()

    def isatty(self):
        return self.original.isatty()

    def seek(self, pos, mode=0):
        return self.original.seek(pos, mode)

    def tell(self):
        return self.original.tell()

    def read(self, n=-1):
        return self.original.read(n)

    def readline(self, length=None):
        return self.original.readline(length)

    def readlines(self, sizehint=0):
        return self.original.readlines(sizehint)

    def truncate(self, size=None):
        return self.original.truncate(size)


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

        suite = self._getSuite(newSuite=True)
        loader = runner.TestLoader()
        suite.run(loader.loadClass(SkipperTester))
        self.failIf(SkipperTester.errorStr, SkipperTester.errorStr)


allMethods = ('setUpClass', 'setUp', 'tearDown', 'tearDownClass', 'method')

class FunctionalTest(common.RegistryBaseMixin, unittest.TestCase):
    """
    """
    cpp = None

    def setUp(self):
        common.RegistryBaseMixin.setUp(self)
        sys.stdout = _StdioProxy(sys.stdout)
        sys.stderr = _StdioProxy(sys.stderr)
        self.loader = runner.TestLoader()

    def tearDown(self):
        common.RegistryBaseMixin.tearDown(self)
        sys.stdout = sys.stdout.original
        sys.stderr = sys.stderr.original

    def testBrokenSetUp(self):
        self.suite.run(self.loader.loadClass(erroneous.TestFailureInSetUp))
        imi = self.reporter.udeMethod
        self.assertEqual(imi.name, 'setUp')
        self.assert_(len(self.reporter.errors) > 0)
        self.assert_(isinstance(self.reporter.errors[0][1].value,
                                erroneous.FoolishError))

    def testBrokenTearDown(self):
        self.suite.run(self.loader.loadClass(erroneous.TestFailureInTearDown))
        imi = self.reporter.udeMethod
        self.assertEqual(imi.name, 'tearDown')
        errors = self.reporter.errors
        self.assert_(len(errors) > 0)
        self.assert_(isinstance(errors[0][1].value, erroneous.FoolishError))

    def testBrokenSetUpClass(self):
        self.suite.run(self.loader.loadClass(
            erroneous.TestFailureInSetUpClass))
        imi = self.reporter.udeMethod
        self.assertEqual(imi.name, 'setUpClass')
        self.assert_(self.reporter.errors)

    def testBrokenTearDownClass(self):
        self.suite.run(self.loader.loadClass(
            erroneous.TestFailureInTearDownClass))
        imi = self.reporter.udeMethod
        self.assertEqual(imi.name, 'tearDownClass')

    def testHiddenException(self):
        self.suite.run(self.loader.loadMethod(
            erroneous.DemoTest.testHiddenException))
        self.assertSubstring(erroneous.HIDDEN_EXCEPTION_MSG, self.reporter.out)

    def testLeftoverSockets(self):
        self.suite.run(self.loader.loadMethod(
            erroneous.SocketOpenTest.test_socketsLeftOpen))
        self.assert_(self.reporter.cleanerrs)
        self.assert_(isinstance(self.reporter.cleanerrs[0].value, util.DirtyReactorWarning))

    def testLeftoverPendingCalls(self):
        self.suite.run(self.loader.loadMethod(
            erroneous.ReactorCleanupTests.test_leftoverPendingCalls))
        errors = self.reporter.errors
        self.assert_(len(errors) > 0)
        self.assert_(isinstance(errors[0][1].value, util.PendingTimedCallsError))

    def testTimingOutDeferred(self):
        origTimeout = util.DEFAULT_TIMEOUT_DURATION
        util.DEFAULT_TIMEOUT_DURATION = 0.1
        try:
            self.suite.run(self.loader.loadClass(erroneous.TimingOutDeferred))
        finally:
            util.DEFAULT_TIMEOUT_DURATION = origTimeout 
        self.assertSubstring("FAILED (errors=1, successes=3)", self.reporter.out)

    def testPyUnitSupport(self):
        self.suite.run(self.loader.loadClass(pyunit.PyUnitTest))

    def testClassTimeoutAttribute(self):
        """test to make sure that class-attribute timeout works"""
        self.suite.run(self.loader.loadClass(
            timeoutAttr.TestClassTimeoutAttribute))
        errors = self.reporter.errors
        self.assert_(len(errors) > 0)
        errors[0][1].trap(defer.TimeoutError)

    def testCorrectNumberTestReporting(self):
        """make sure trial reports the correct number of tests run (issue 770)"""
        self.suite.run(self.loader.loadModule(numOfTests))
        self.assertSubstring("Ran 1 tests in", self.reporter.out)


class SuppressionTest(unittest.TestCase):
    def setUp(self):
        self.stream = StringIO()
        self._stdout, sys.stdout = sys.stdout, self.stream
        self.suite = runner.TrialRoot(reporter.Reporter(self.stream))
        self.loader = runner.TestLoader()

    def tearDown(self):
        sys.stdout = self._stdout
        self.stream = None
    
    def getIO(self):
        return self.stream.getvalue()

    def testSuppressMethod(self):
        self.suite.run(self.loader.loadMethod(
            suppression.TestSuppression.testSuppressMethod))
        self.assertNotSubstring(suppression.METHOD_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.MODULE_WARNING_MSG, self.getIO())

    def testSuppressClass(self):
        self.suite.run(self.loader.loadMethod(
            suppression.TestSuppression.testSuppressClass))
        self.assertSubstring(suppression.METHOD_WARNING_MSG, self.getIO())
        self.assertNotSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.MODULE_WARNING_MSG, self.getIO())

    def testSuppressModule(self):
        self.suite.run(self.loader.loadMethod(
            suppression.TestSuppression2.testSuppressModule))
        self.assertSubstring(suppression.METHOD_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertNotSubstring(suppression.MODULE_WARNING_MSG, self.getIO())

    def testOverrideSuppressClass(self):
        self.suite.run(self.loader.loadMethod(
            suppression.TestSuppression.testOverrideSuppressClass))
        self.assertSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.MODULE_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.METHOD_WARNING_MSG, self.getIO())

        
FunctionalTest.timeout = 30.0
